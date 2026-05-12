# Restriction-Rewriting Architecture

## v0.5: bipartite cellular sheaf with cost-asymmetric evidence

This architecture builds a knowledge layer by stitching papers into a coherent set of ideas. The core object is a bipartite cellular sheaf whose two vertex types are **claims** and **evidence-pieces**. Edges run from a claim to each evidence-piece it predicts at.

The key modeling choice is epistemic asymmetry:

- Evidence cores are fixed: the system does not modify measurements.
- Evidence context can be inferred, but only at high cost and with explicit provenance.
- Claim interpretations are rewriteable: most reconciliation should happen by narrowing, weakening, or otherwise clarifying claims.

The output is not just a graph of papers. It is a structured layer of Ideas: coherent cross-paper knowledge units with supporting evidence, rewritten claims, unresolved tensions, and suggested next steps.

## Core Structure

The corpus is represented as a bipartite complex:

```text
claims  --->  evidence-pieces
```

There are two disjoint vertex sets:

- `C`: claim vertices, one per extracted scientific claim.
- `V`: evidence vertices, one per extracted observation, measurement, simulation result, theorem, or reported artifact.

An edge `(c, v)` exists when claim `c` makes a prediction about evidence-piece `v`. A single claim can predict many evidence-pieces, and a single evidence-piece can be predicted by many claims.

Papers are not structural vertices. They are provenance groupings over claims and evidence.

## Vertex Stalks

### Claim vertices

Each claim vertex has an interpretation stalk:

```text
F(c) = R^{k_c}
```

The default implementation uses:

```text
x_c = (in_regime_strength, out_regime_strength)
```

with initial value:

```text
x_c_init = (1.0, 1.0)
```

This means the claim is initially asserted at full strength both inside and outside its home regime. A common rewrite moves the claim to something like:

```text
x_c_final = (1.0, 0.2)
```

which preserves the claim in its home regime but weakens its out-of-regime predictions.

The interpretation stalk can be expanded when a claim needs richer scope parameters, such as framework, geometry, scale, organism, instrument, dataset, or modeling assumption.

### Evidence vertices

Each evidence vertex has a stalk with two parts:

```text
F(v) = core(v) ⊕ context(v)
```

The **core** contains the actual reported observation. It is hard-fixed.

The **context** contains implicit regime parameters that may not have been explicitly encoded at extraction time. Context values start unspecified or zero and can be filled only at high cost.

Examples:

- Core: "m=1 fluctuations remain low at experimental shear."
- Context: "linear ideal MHD framework", "Bennett profile", "rainfall regularity", "short-scale kinetic regime."

Evidence-context filling is not evidence mutation. It is an auditable claim that the corpus needs an omitted contextual distinction in order to cohere.

## Edges

An edge `(c, v)` means:

```text
claim c predicts at evidence-piece v
```

Each edge stores:

- `claim_id`
- `evidence_id`
- `base_prediction`: what the claim predicts at the evidence point under full assertion.
- `regime_tag`: whether the evidence point is inside the claim's home regime.
- `edge_stalk`: the comparison space for the evidence core.
- `prediction_rationale`: natural-language explanation of the prediction.
- `provenance`: source spans, extraction model, human review status, and confidence.

The edge stalk is:

```text
F(c, v) = R^{dim core(v)}
```

In simple demonstrations this is often one-dimensional. In real corpora it should usually be a typed vector with units, uncertainty, and variable names.

## Restriction Maps

Each edge has two restriction maps into the edge stalk:

```text
R_claim_to_edge: F(c) -> F(c, v)
R_evidence_to_edge: F(v) -> F(c, v)
```

The evidence restriction projects the fixed evidence core into the comparison space:

```text
R_evidence_to_edge(x_v) = core(v)
```

The claim restriction computes the claim's prediction at `v`, modulated by the claim interpretation and any relevant evidence context:

```text
R_claim_to_edge(x_c, context(v)) = predicted_at_v
```

The current scalar implementation uses an affine blend:

```text
predicted_at_v = strength * base_prediction
               + (1 - strength) * actual_core(v)
```

where:

```text
strength = in_regime_strength   if v is in the claim's home regime
strength = out_regime_strength  otherwise
```

This gives a useful interpretation:

- `strength = 1`: full assertion of the claim's prediction.
- `strength = 0`: no opinion at this evidence point, so the prediction collapses to the actual core and creates no residual.

For richer domains, `R_claim_to_edge` can be a typed prediction function rather than a scalar formula. The important invariant is that its output is comparable to the evidence core at `v`.

## Residual

The edge residual is:

```text
(δx)_{c,v} = R_claim_to_edge(x_c, context(v))
           - R_evidence_to_edge(x_v)
```

or:

```text
residual(c, v) = predicted_at_v - actual_at_v
```

Large residuals identify specific claim-evidence tensions. Attribution is direct: the source claim on the edge is the claim whose prediction failed at that evidence-piece.

## Objective

The optimizer minimizes:

```text
total_objective =
    ||δx||^2
  + λ_claim * Σ_c ||x_c - x_c_init||^2
  + λ_context * Σ_v ||context(v) - context_init(v)||^2
  + ∞ * Σ_v ||core(v) - core_init(v)||^2
```

with typical default weights:

```text
λ_claim = 1.0
λ_context = 5.0
```

This makes claim rewriting cheaper than evidence-context filling, while evidence-core modification is forbidden.

The objective formalizes the intended reading discipline:

1. First, see whether claims can be scoped more carefully.
2. If that is insufficient, infer missing context only when the residual strongly justifies it.
3. Never change reported measurements to improve coherence.

## Rewrite Operations

The system has three operation classes.

### 1. Claim interpretation rewrite

Move `x_c` within the claim stalk. This is the preferred operation.

Examples:

- Narrow an out-of-regime generalization.
- Demote a causal claim to a correlation.
- Restrict a theoretical claim to its modeling framework.
- Split a broad claim into multiple scoped claims.

### 2. Evidence-context filling

Move `context(v)` away from its initial unspecified value. This is expensive and must be explicitly flagged.

Examples:

- Infer that a result depends on a hidden rainfall regime.
- Add an omitted instrument calibration context.
- Mark a simulation result as belonging to a specific numerical closure or boundary condition.

### 3. Evidence-core modification

Forbidden. The original reported observation is treated as sacred data. If the source paper is later found to contain an error, that should enter as a new evidence item or provenance correction, not as silent core mutation.

## Schemas

### Evidence

```json
{
  "evidence_id": "obs_eig_m1_growth",
  "paper_id": "eigenmode_zpinch",
  "label": "gamma t_a ~ 0.7 m=1 NOT stabilized at experimental shear",
  "core": {
    "dimensions": [
      {
        "name": "m1_stabilized",
        "value": 0.0,
        "scale": "normalized_binary",
        "uncertainty": null,
        "source_span": "..."
      }
    ],
    "locked": true
  },
  "context": {
    "dimensions": [
      {
        "name": "framework",
        "value": 0.0,
        "label": "linear ideal MHD framework / profile family tested",
        "filled_by_pipeline": false,
        "source_span": "..."
      }
    ]
  },
  "provenance": {
    "extractor": "llm_or_human",
    "confidence": 0.82,
    "review_status": "unreviewed"
  }
}
```

### Claim

```json
{
  "claim_id": "S_02",
  "paper_id": "shumlak2009",
  "label": "0.1 k V_A is the m=1 stabilization threshold",
  "stalk_basis": ["in_regime_strength", "out_regime_strength"],
  "x_init": [1.0, 1.0],
  "x_final": [1.0, 0.2],
  "weaknesses": [
    "uniform-shear derivation",
    "single wavelength tested",
    "causality not established"
  ],
  "rewrite_history": [
    {
      "operation": "narrow_to_uniform_shear_window",
      "from": [1.0, 1.0],
      "to": [1.0, 0.2],
      "distance": 0.8,
      "justification": "Preserves the ZaP-window observation while weakening out-of-regime MHD generalization."
    }
  ],
  "provenance": {
    "source_span": "...",
    "extractor": "llm_or_human",
    "confidence": 0.79,
    "review_status": "unreviewed"
  }
}
```

### Claim-evidence edge

```json
{
  "edge_id": "S_02__obs_eig_m1_growth",
  "claim_id": "S_02",
  "evidence_id": "obs_eig_m1_growth",
  "base_prediction": {
    "dimensions": [
      {
        "name": "m1_stabilized",
        "value": 1.0,
        "scale": "normalized_binary"
      }
    ]
  },
  "regime_tag": "out_of_regime",
  "prediction_rationale": "If the threshold claim is asserted out of regime, the eigenmode calculation should also show m=1 stabilization at experimental shear.",
  "residual": {
    "initial": 1.0,
    "final": 0.04
  },
  "provenance": {
    "prediction_generated_by": "llm_or_human",
    "confidence": 0.68,
    "review_status": "needs_domain_review"
  }
}
```

### Sheaf state

```json
{
  "sheaf_id": "shumlak_v05",
  "version": "v0.5_bipartite",
  "claim_vertices": ["S_01", "S_02", "E_02"],
  "evidence_vertices": ["obs_zap_m1", "obs_eig_m1_growth"],
  "edges": ["S_02__obs_zap_m1", "S_02__obs_eig_m1_growth"],
  "objective": {
    "initial_residual": 4.0,
    "final_residual": 2.08,
    "claim_rewrite_distance": 0.8,
    "context_fill_distance": 0.0
  },
  "remaining_tensions": [
    {
      "edge_id": "E_02__obs_zap_m1",
      "residual": 1.0,
      "interpretation": "The linear-MHD claim predicts no stability where ZaP observes stability."
    }
  ]
}
```

### Idea

```json
{
  "idea_id": "idea_01_m1_real_but_nonMHD",
  "title": "m=1 stabilization at experimental shear is real but linear MHD does not explain it",
  "scope": {
    "system": "flowing Z-pinch",
    "regime": "experimental shear, non-ideal effects likely relevant"
  },
  "contributing_claims": ["S_01", "S_02", "E_02", "E_05", "G_03", "G_04"],
  "contributing_evidence": ["obs_zap_m1", "obs_eig_m1_growth"],
  "tensions_resolved": [
    {
      "edge_id": "S_02__obs_eig_m1_growth",
      "resolution": "S_02 narrowed to the ZaP-window / uniform-shear regime."
    }
  ],
  "open_questions": [
    {
      "question": "Which non-ideal mechanism explains the observed m=1 stabilization?",
      "priority": "high",
      "suggested_next_steps": ["simulation", "theory_extension", "corpus_expansion"]
    }
  ],
  "transitions_out": ["idea_03_linear_MHD_boundaries"]
}
```

## Pipeline

### Stage 1: Extract evidence and claims

For each paper, extract evidence and claims separately.

Evidence extraction captures fixed observations with basis, units, uncertainty, source spans, and provenance.

Claim extraction captures statements with source spans, acknowledged limitations, home regime, and possible predictive targets.

### Stage 2: Build evidence comparability

Identify evidence-pieces that live in comparable observational spaces or nearby regimes. This is not yet the sheaf edge set; it is a candidate map of where predictions may be meaningful.

Useful comparability signals include:

- Shared observable.
- Shared physical system.
- Shared task or benchmark.
- Shared model class.
- Regime overlap or regime containment.
- Explicit citation or critique.

### Stage 3: Generate claim-evidence prediction edges

For each claim and candidate evidence-piece, ask whether the claim predicts anything at that evidence-piece.

If yes, create an edge `(c, v)` with:

- A base prediction.
- A regime tag.
- A rationale.
- A confidence score.
- Provenance for the source text used to construct the prediction.

Edges should be sparse. A claim should not connect to every evidence-piece by default.

### Stage 4: Build the bipartite sheaf

Create claim vertices, evidence vertices, and claim-evidence edges.

Build the residual operator from the current prediction functions:

```text
δ(c, v) = predicted_at_v - actual_at_v
```

For nonlinear prediction functions, this is an evaluation operator rather than a single fixed global matrix.

### Stage 5: Compute residuals

Evaluate all edge residuals under the current assignments.

Rank tensions by:

- Residual magnitude.
- Edge confidence.
- Scientific importance.
- Whether the tension is central to an emerging Idea.

### Stage 6: Generate rewrite candidates

For each high-residual edge, generate candidate rewrites for the source claim.

The rewrite prompt should require candidates to:

1. Preserve the claim's home-regime evidence when appropriate.
2. Reduce the target edge residual.
3. Invoke an acknowledged limitation, scope condition, or framework boundary.
4. Produce a reader-verifiable natural-language rewrite.
5. Report a rewrite distance and justification.

Candidate rewrites can include:

- Scope narrowing.
- Framework restriction.
- Regime split.
- Causal-to-correlational demotion.
- Mechanism substitution when supported by other claims.
- Claim split into multiple child claims.

### Stage 7: Score operations

Score each candidate operation by the full objective:

```text
new_residual
+ λ_claim * claim_rewrite_distance
+ λ_context * context_fill_distance
```

Evidence-context fills may be proposed when claim rewrites cannot explain the residual without inventing unsupported claim content.

Adopt the operation that most improves the objective while preserving provenance and evidence-faithfulness constraints.

### Stage 8: Iterate

After each accepted operation, recompute residuals. Continue until:

- No proposed operation improves the objective.
- The residual is below a chosen tolerance.
- A maximum iteration budget is reached.
- Human review is required because high-impact low-confidence rewrites dominate the next step.

### Stage 9: Consolidate Ideas

Group the stabilized sheaf into Ideas. An Idea is a coherent cross-paper knowledge unit with:

- Scope.
- Contributing claims.
- Contributing evidence.
- Rewrites and context fills.
- Resolved tensions.
- Remaining tensions.
- Open questions.
- Typed suggested next steps.
- Transitions to related Ideas.

Ideas are the main user-facing knowledge layer.

## Mathematical Framing

The architecture is a sheaf-inspired inverse problem over a bipartite cellular complex.

The state consists of:

```text
x = ({x_c}_{c in C}, {x_v}_{v in V})
```

where:

- `x_c` is the current claim interpretation.
- `x_v = (core(v), context(v))`.
- `core(v)` is fixed.
- `context(v)` is optimization-visible but expensive.

For each edge `(c, v)`:

```text
δ_{c,v}(x) = R_claim_to_edge(x_c, context(v)) - R_evidence_to_edge(x_v)
```

The optimization is:

```text
minimize_x  Σ_{(c,v)} ||δ_{c,v}(x)||^2
          + λ_claim Σ_c ||x_c - x_c_init||^2
          + λ_context Σ_v ||context(v) - context_init(v)||^2

subject to core(v) = core_init(v) for all evidence vertices v
```

In practice, optimization is usually discrete or hybrid:

- The LLM proposes interpretable candidate rewrites and context fills.
- The system scores them numerically.
- Human review can accept, reject, or edit high-impact operations.

This favors interpretability over global continuous optimality.

## Diagnostics

### Residual diagnostics

The primary diagnostic is the edge residual:

```text
residual(c, v) = predicted_at_v - actual_at_v
```

This answers:

- Which claim failed to predict which evidence-piece?
- Did rewriting the claim reduce the failure?
- Did the residual move elsewhere after the rewrite?

### Linearized spectral diagnostics

When prediction functions are nonlinear, a global sheaf Laplacian is no longer the whole story. A linearized operator can still be useful around the current state:

```text
J = derivative of δ at current x
L = J^T J
```

The spectrum of `L` is a local sensitivity diagnostic. It can reveal flat directions, fragile directions, and degeneracies in the current encoding.

It should not be treated as the primary proof of global coherence in the nonlinear setting.

### Remaining residuals

If residual remains after all allowed rewrites and context fills, call it an unresolved obstruction under the current model and candidate set.

Do not automatically identify this residual with sheaf cohomology. In the nonlinear, candidate-generated setting, it is more precise to say:

```text
the corpus is still far from a global section under the available operations
```

This may mean:

- The corpus contains a genuine contradiction.
- The evidence representation is too coarse.
- The prediction edge was extracted incorrectly.
- The candidate rewrite set was incomplete.
- External information is needed.

## Provenance and Auditability

Every generated object should carry provenance:

- Source paper.
- Source span.
- Extractor identity.
- Extraction confidence.
- Human review status.
- Rewrite rationale.
- Whether context was explicit in source text or inferred by the pipeline.

Outputs must clearly distinguish:

- Original evidence core.
- Extracted or normalized evidence representation.
- Inferred context.
- Original claim.
- Rewritten claim.
- Model-generated prediction edge.

The reader should always be able to ask: "Did the paper actually say this, or did the pipeline infer it?"

## Implementation Plan

1. Define schemas for evidence, claims, claim-evidence edges, sheaf state, operations, and Ideas.
2. Implement extraction for evidence cores, evidence context candidates, claims, and claim weaknesses.
3. Implement sparse claim-evidence edge generation with confidence and provenance.
4. Implement residual evaluation for scalar and typed-vector evidence cores.
5. Implement candidate operation generation for claim rewrites and context fills.
6. Implement objective scoring and iteration.
7. Implement Idea consolidation from final sheaf state.
8. Implement visualizations for claim/evidence graph, residuals, rewrites, context fills, and Ideas.

## Milestones

### Milestone 1: Known small corpus

Run the pipeline on the Shumlak three-paper corpus. Confirm that:

- Cross-paper tensions localize to specific claim-evidence edges.
- The threshold claim narrows rather than forcing evidence changes.
- Evidence-context filling does not trigger when claim rewriting is sufficient.
- Ideas expose actionable scientific conclusions.

### Milestone 2: Context-fill corpus

Run on a corpus where missing context is structurally necessary. Confirm that:

- Claim rewrites alone cannot resolve the residual.
- Evidence context fills only after the residual justifies the higher cost.
- The output explicitly flags inferred context as inferred.

### Milestone 3: Larger corpus

Scale to a larger research landscape. Confirm that:

- Edge generation remains sparse and meaningful.
- Residual ranking remains interpretable.
- Idea consolidation produces useful cross-paper concepts rather than paper clusters.
- Human review effort is concentrated on high-impact, low-confidence edges and rewrites.

## Limitations

### Claim-to-prediction operationalization is the hardest step

The weak link is translating natural-language claims into structured predictions. This needs source spans, confidence, and domain review. The sheaf can only diagnose tensions in the prediction graph it is given.

### Evidence representation can be too coarse

If the evidence core or context basis omits the variable needed to explain a distinction, the system may misattribute residual to a claim. Context-fill operations and schema expansion are the safety valve, but they require careful review.

### The optimization is candidate-limited

The system finds the best operation among proposed candidates, not the global optimum over all possible scientific interpretations. This is intentional: interpretable rewrites are more useful than opaque continuous parameter updates.

### Nonlinear predictions weaken global spectral claims

Linearized Laplacians are useful local diagnostics, but the main coherence measure is the evaluated residual objective.

### Hidden confounders remain hard

If the needed explanatory variable appears nowhere in the corpus, the system can flag unresolved residual but cannot responsibly invent the missing fact. That should become an open question or corpus-expansion task.

## Summary

The v0.5 architecture treats knowledge synthesis as disciplined restriction rewriting. Claims make predictions at evidence-pieces; residuals show exactly where those predictions fail; cheap claim rewrites and expensive context fills search for a coherent reading without altering measurements.

The final knowledge layer is a set of Ideas: scoped, auditable, cross-paper units that preserve evidence, expose rewritten interpretations, and make remaining uncertainty actionable.
