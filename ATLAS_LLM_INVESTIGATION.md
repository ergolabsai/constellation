# Atlas Constellation LLM Investigation Brief

Use this markdown file as a single handoff prompt for an LLM that needs to investigate what the Atlas constellation means. It is written to work on its own, but it also points to local artifacts if the LLM has file access.

## Prompt To The LLM

You are investigating a scientific knowledge graph called the Atlas Constellation. Treat it as a hypothesis map, not as a final proof. Your job is to explain what the constellation means, identify the strongest and weakest scientific links, and propose the next investigation steps.

Work like a careful research collaborator:

- Distinguish source evidence from model interpretation.
- Do not mutate evidence cores. Evidence values are fixed reported observations.
- Treat claim rewrites as scope changes, not as proof that the old claim was false.
- Use claim IDs, evidence IDs, and idea IDs when making assertions.
- When uncertain, say what would need to be checked in the original papers.
- Prefer concrete, source-checkable questions over broad speculation.

If you have access to the repository, inspect these files:

- `ARCHITECTURE.md`: conceptual model.
- `runs/atlas_run/report.md`: human-readable summary.
- `runs/atlas_run/constellation.html`: interactive visualization.
- `runs/atlas_run/sheaf.json`: full claim/evidence/edge/residual object.
- `runs/atlas_run/prediction_edges.json`: generated claim-to-evidence predictions.
- `runs/atlas_run/operations.json`: accepted claim rewrites.
- `runs/atlas_run/claims/*.json`: claim records.
- `runs/atlas_run/evidence/*.json`: evidence records.
- `runs/atlas_run/ideas/*.json`: idea records.
- `corpora/atlas/pdfs/*.pdf`: original papers.

## What This System Is

The architecture is a bipartite cellular sheaf over scientific literature.

There are two vertex types:

- Claims: scientific claims extracted from papers.
- Evidence: observations, measurements, simulations, theorems, or reported artifacts.

Edges mean: a claim predicts something at an evidence piece.

Papers are not graph vertices. They are provenance containers for claims and evidence.

The core modeling asymmetry:

- Evidence cores are fixed.
- Evidence context can be filled only at high cost.
- Claim interpretations can be rewritten by narrowing, weakening, or clarifying scope.

The default claim state is:

```text
[in_regime_strength, out_regime_strength]
```

A claim starts at `[1.0, 1.0]`, meaning it is asserted at full strength both in and out of its home regime. A rewrite such as `[1.0, 0.6]` preserves the claim in its home regime while weakening its out-of-regime force.

Residuals identify tensions. If a claim predicts one value and an evidence core reports another, the edge gets a residual. Lower residual means the constellation is more coherent after allowed rewrites.

## Visualization Encoding

In the Atlas visualization:

- Kumar/Atlas claims are gold stars.
- Kumar/Atlas evidence pieces are gold diamonds.
- Non-Kumar claims are circles.
- Non-Kumar evidence pieces are squares.
- Blobs are ideas: coherent claim/evidence knowledge units.
- Edge color shows residual magnitude.
- Dashed claim rings indicate rewritten claims.

## Current Atlas Run

The current run is:

```text
Papers: 21
Claims: 30
Evidence pieces: 25
Claim-evidence edges: 63
Ideas: 6
Initial residual: 3.000
Final residual: 1.080
Claim rewrite distance: 1.200
Context fill distance: 0.000
```

Interpretation: the graph initially had three strong cross-regime tensions. The optimizer reduced them by narrowing three claims out of regime, while leaving evidence untouched.

## Accepted Rewrites

| Claim | Rewrite | Residual Change | Interpretation |
| --- | --- | --- | --- |
| AN_01 | 1, 1 -> 1, 0.6 | 1 -> 0.36 | Angus 2020 remains strong in its tested shear-only regime, but weakens when projected onto the Atlas H3 regime. |
| B_01 | 1, 1 -> 1, 0.6 | 1 -> 0.36 | Bondeson-Iacono remains strong for rotation without the Atlas H3 structure, but weakens outside that regime. |
| N_01 | 1, 1 -> 1, 0.6 | 1 -> 0.36 | Newcomb's static finite-beta obstruction remains strong in the static regime, but weakens when applied to rotating helical H3 configurations. |

These are scope rewrites. They do not say the older papers are wrong. They say those claims should not be treated as full-strength objections everywhere.

## Six Ideas To Investigate

| # | Idea ID | Title | Claims | Evidence | Remaining Tensions |
| --- | --- | --- | ---: | ---: | ---: |
| 1 | idea_01_m1_stability_via_H3 | m=1 stability of rotating helical Z-pinch is closed by the H3 quartic Alfven minimum | 10 | 9 | 3 |
| 2 | idea_02_static_obstruction_genealogy | The static finite-beta m=1 obstruction survives as a special-case limit | 6 | 6 | 0 |
| 3 | idea_03_hall_regularization | Hall corrections at finite d_i/R regularize the H3 singularity over a d_i layer | 5 | 3 | 0 |
| 4 | idea_04_sari_boundary | Atlas's regime ends at M_A=1 where SARI continuum overlap takes over | 6 | 5 | 0 |
| 5 | idea_05_shumlak_m0_complementary | Shumlak's m=0 sheared-flow stabilization is complementary rather than competing | 6 | 5 | 0 |
| 6 | idea_06_mathematical_and_numerical_foundations | Beltrami, operator, and numerical foundations support the Atlas construction | 6 | 5 | 0 |

## Open Questions And Attached Work

Each open question now carries concrete next-work ideas. Use these as starting hypotheses, not as a fixed research plan.

### idea_01_m1_stability_via_H3

Priority: high

Question: Which finite-device and nonlinear effects are still outside the H3 ideal-MHD closure?

- Simulation: finite-length Atlas profile scan. Run resistive and nonlinear MHD on RIGID-BELTRAMI-A-like profiles with finite-length boundaries.
- Theory: nonlinear remainder bound. Identify which nonlinear terms are excluded by H1-H5 and bound how large they can be before closure fails.
- Experiment: profile-realizability diagnostic. Design diagnostics that can confirm H3 quartic structure and sub-Alfvenic rotation.

Priority: blocking

Question: Which remaining residuals are real contradictions rather than seeded-scope artifacts?

- Audit: residual edge review. Check high-residual edges against source PDFs.
- Theory: scope split proposal. Split broad claims into home-regime and cross-regime claims when residuals are real.

### idea_02_static_obstruction_genealogy

Priority: medium

Question: Where exactly does the static Newcomb obstruction stop applying once helical rotation and H3 are present?

- Theory: assumption homotopy. Map Newcomb's static operator into the Atlas helical-flow operator assumption by assumption.
- Simulation: static-to-H3 profile continuation. Track the m=1 eigenvalue while continuing from static profiles to H3 profiles.
- Literature: comparator source audit. Compare Newcomb, Bondeson-Iacono, and Angus assumptions against Atlas H1-H5.

### idea_03_hall_regularization

Priority: high

Question: Does the n^-4 accumulation survive at finite d_i/R, or is it replaced by a Hall-modified spectrum?

- Simulation: Hall-MHD d_i/R sweep. Track spectral accumulation as d_i/R increases.
- Theory: matched asymptotic H3 layer. Derive the inner Hall layer correction and match it to the outer ideal-MHD solution.
- Experiment: Hall-scale sensitivity check. Estimate whether available devices operate at d_i/R large enough for Hall effects to dominate.

### idea_04_sari_boundary

Priority: medium

Question: How wide is the transition region as M_A approaches 1 from below?

- Simulation: approach M_A = 1 from below. Sweep M_A upward and track least-stable non-axisymmetric modes.
- Theory: transition-width asymptotics. Derive scaling for residual growth near M_A = 1.
- Experiment: rotation-boundary measurement. Determine whether devices can stay below the SARI boundary.

### idea_05_shumlak_m0_complementary

Priority: exploratory

Question: Can a ZaP or FuZE-class device realize a profile satisfying both Shumlak m=0 shear and Atlas m=1 H3 conditions?

- Experiment: joint m=0/m=1 profile target. Design a discharge satisfying both stabilization stories.
- Simulation: common-profile stability check. Run one equilibrium through both m=0 and m=1 analyses.
- Theory: mode-family coupling. Derive whether simultaneous m=0 and m=1 closure creates higher-m constraints.

### idea_06_mathematical_and_numerical_foundations

Priority: medium

Question: Which foundation pieces need direct validation before they can support the Atlas construction?

- Theory: foundation-to-H1-H5 map. Map Chandrasekhar-Kendall, Mahajan-Yoshida, Hameiri, and Frieman assumptions onto the Atlas H1-H5 requirements.
- Simulation: independent spectral benchmark. Run the Atlas equilibrium through a Legolas-style or shooting-method benchmark and compare eigenvalues against the seeded pseudospectral result.
- Audit: foundational source audit. Verify each foundation source is being used at its native scope instead of being promoted into direct experimental evidence.

## Working Interpretation

The constellation is saying that Kumar/Atlas is not simply another paper in the same pile. It proposes a structural regime distinction:

```text
Static or shear-only Z-pinch obstruction
    is not the same as
Rotating helical Z-pinch with H1-H5, especially H3 quartic Alfven minimum.
```

The older obstruction literature remains valid in its home regimes. The Atlas claim is that the H3 structure creates a regime in which the m=1 obstruction is closed under ideal MHD assumptions, below the SARI boundary and in the d_i/R -> 0 limit.

The main scientific question is not "Is Newcomb wrong?" It is:

```text
Exactly which assumptions move the system out of Newcomb/Bondeson/Angus obstruction territory and into the Atlas-stable territory?
```

## Claim Index

Claim state is `[in_regime_strength, out_regime_strength]`.

| Claim | Paper | Label | Final State |
| --- | --- | --- | --- |
| AN_01 | angus2020 | Linear shear flow alone does not stabilize m=1 kink across realistic Z-pinch profile classes | 1, 0.6 |
| AN_02 | angus2020 | Required shear for m=0 stabilization scales with profile-dependent shear-free growth; m=1 needs a different mechanism | 1, 1 |
| A_01 | atlas2026 | 5 constraints H1-H5 are necessary and sufficient for m=1 stability in rotating helical Z-pinch | 1, 1 |
| A_02 | atlas2026 | H3 quartic Alfven minimum is the structural ingredient absent from shear-flow-only treatments | 1, 1 |
| A_03 | atlas2026 | Discrete spectrum near quartic continuum minimum accumulates as n^-4 with sharp exponent | 1, 1 |
| A_04 | atlas2026 | Bi-orthogonal Picone identity generalizes Newcomb node-counting to non-self-adjoint operators | 1, 1 |
| A_05 | atlas2026 | Below SARI bound M_A<1, ideal-MHD m=1 growth rate is zero in the asymptotic d_i/R -> 0 regime | 1, 1 |
| A_06 | atlas2026 | Framework closes prior conjectures around helical flow, Hameiri Sturmian structure, n^-4 sharpness, SARI exclusion, and kink obstruction | 1, 1 |
| A_07 | atlas2026 | RIGID-BELTRAMI-A double-Beltrami equilibrium achieves beta=12.3% with all H1-H5 satisfied | 1, 1 |
| BR_01 | brughmans2024 | Non-axisymmetric SARI modes are confirmed numerically by Legolas with growth rates comparable to MRI | 1, 1 |
| B_01 | bondeson1989 | In toroidal or cylindrical geometry, rotation mitigates but does not eliminate kink at finite pressure | 1, 0.6 |
| CK_01 | chandrasekhar1957 | Force-free curl H = alpha H fields admit poloidal and toroidal eigenfunction solutions | 1, 1 |
| CL_01 | claes2020 | Legolas finite-element MHD spectroscopy computes the full eigenspectrum for 1D equilibria with flow | 1, 1 |
| CR_01 | crews2024 | Kadomtsev interchange criterion has an entropy-gradient interpretation analogous to Schwarzschild-Ledoux | 1, 1 |
| DJ_01 | dejonghe2022 | Legolas extension with viscosity and Hall current is benchmarked against historic results | 1, 1 |
| FR_01 | frieman1960 | Linear MHD stability with stationary flow is governed by a non-Hermitian operator | 1, 1 |
| GK_01 | goedbloed2022 | Super-Alfvenic Rotational Instability emerges from overlap of Doppler-shifted Alfven continua | 1, 1 |
| GK_02 | goedbloed2022 | At M_A >= 1 continuum overlap opens uncontrolled SARI spectrum | 1, 1 |
| H_01 | hameiri1981 | Sufficient stability conditions for rotating screw-pinch follow from circle theorems and spectral bounds | 1, 1 |
| H_02 | hameiri1985 | Essential spectrum of ideal MHD with flow consists of Doppler-shifted Alfven and slow continua | 1, 1 |
| ML_01 | mahajan2024 | Hall MHD waves are fundamentally distinct from MHD waves at d_i scales | 1, 1 |
| MY_01 | mahajan1998 | Coupled magnetofluid admits two-parameter double-Beltrami equilibria with non-trivial flow and pressure | 1, 1 |
| N_01 | newcomb1960 | Static Z-pinch at finite pressure cannot be linearly stable to m=1 in ideal MHD | 1, 0.6 |
| N_02 | newcomb1960 | Number of unstable eigenvalues equals number of interior nodes of the marginal mode | 1, 1 |
| SE_01 | sainterme2026 | In the Hall regime, global whistler instabilities grow significantly faster than ideal-MHD modes | 1, 1 |
| SH_01 | shiraishi2005 | Hall effect regularizes the Alfven singularity over a layer of thickness about d_i | 1, 1 |
| S_01 | shumlak1995 | Sheared axial flow v'/(kV_A) above about 0.1 stabilizes the m=0 sausage mode in static Z-pinch | 1, 1 |
| S_02 | shumlak2001 | ZaP experiment observes a long stable period coincident with sheared sub-Alfvenic flow | 1, 1 |
| W_01 | wang2022 | Axisymmetric SMRI is directly observed in a liquid-metal Taylor-Couette experiment | 1, 1 |
| Z_01 | zhang2019 | FuZE experimentally demonstrates sustained microsecond-scale neutron production during a quiescent period | 1, 1 |

## Evidence Index

Evidence core values are scalar placeholders in this deterministic seed:

- `1` means the evidence supports or instantiates the positive observable.
- `0` means the evidence reports instability, obstruction, failure, or absence for that observable.
- `0.85` is a partial/proportional encoded result.

| Evidence | Paper | Label | Core |
| --- | --- | --- | ---: |
| ev_angus_m0_scaling | angus2020 | m=0 shear-stabilization scaling follows profile-dependent growth-rate scaling | 0.85 |
| ev_angus_m1_persists | angus2020 | m=1 kink remains unstable at all tested shear levels on realistic profiles | 0 |
| ev_atlas_120pts | atlas2026 | All 120 sampled (m,k) points satisfy abs(gamma)<1e-11 tau_A^-1 | 1 |
| ev_atlas_h1_violate | atlas2026 | Violating H1 with q_min=0.92 produces an unstable kink | 0 |
| ev_atlas_h3_value | atlas2026 | abs(F''(r*))/F_max = 0.41/R^2 confirms the H3 quartic minimum | 1 |
| ev_atlas_h3_violate | atlas2026 | Violating H3 gives n^-2 Suydam accumulation and finite growth | 0 |
| ev_atlas_kink_zero | atlas2026 | abs(gamma_m=1) < 8e-12 tau_A^-1 on RIGID-BELTRAMI-A at beta=12.3% | 1 |
| ev_atlas_newcomb_bench | atlas2026 | ARPACK recovers Newcomb 1960 m=1 eigenvalues to 1e-5 relative accuracy | 1 |
| ev_atlas_pseudospec | atlas2026 | epsilon-pseudospectrum boundary stays below 4.1e-7 tau_A^-1 in the upper half-plane | 1 |
| ev_bondeson_toroidal | bondeson1989 | Toroidal rotation mitigates but does not eliminate kink in the cylindrical analogue | 0 |
| ev_brughmans_growth | brughmans2024 | Non-axisymmetric SARI growth rates are comparable to MRI at high mode numbers | 0 |
| ev_chandra_ck | chandrasekhar1957 | Force-free curl H=alpha H is solvable in a poloidal and toroidal basis | 1 |
| ev_crews_entropy | crews2024 | Kadomtsev marginal-stable profile has an entropy-gradient interpretation | 1 |
| ev_friman_overstable | frieman1960 | Stationary-flow MHD operator is non-Hermitian, so overstability is possible | 1 |
| ev_goedbloed_sari | goedbloed2022 | SARI modes fill two-dimensional continua in the eigenfrequency plane at M_A>1 | 0 |
| ev_hameiri_continuum | hameiri1985 | Ideal MHD with flow has Doppler-shifted Alfven continua governing essential spectrum | 1 |
| ev_legolas_bench | claes2020 | Legolas reproduces canonical MHD spectra across benchmark problems | 1 |
| ev_mahajan_db | mahajan1998 | Double-curl Beltrami equilibrium admits non-trivial pressure and minimum-abs(B) confinement | 1 |
| ev_newcomb_static | newcomb1960 | Static finite-beta Z-pinch has unstable m=1 spectrum | 0 |
| ev_sainterme_whistler | sainterme2026 | Global whistler instabilities grow faster than ideal-MHD modes at d_i/L of a few percent | 0 |
| ev_shiraishi_dilayer | shiraishi2005 | Hall-MHD solutions converge to ideal MHD outside a d_i-scale neighborhood of the singularity | 1 |
| ev_shumlak_threshold | shumlak1995 | m=0 stabilization at v'/(kV_A) around 0.1 is demonstrated numerically | 1 |
| ev_shumlak_zap | shumlak2001 | ZaP stable period of 15-20 microseconds is coincident with shear | 1 |
| ev_wang_smri | wang2022 | Axisymmetric SMRI onset is observed at critical magnetic Reynolds number | 0 |
| ev_zhang_neutrons | zhang2019 | FuZE sustains neutron emission during the quiescent period with density-squared scaling | 1 |

## Main Investigation Questions

Use these as the first pass:

1. Explain the six ideas in plain English. What does each idea claim about the literature?
2. For `idea_01_m1_stability_via_H3`, identify the exact assumptions that distinguish the Atlas regime from Newcomb, Bondeson-Iacono, and Angus.
3. Inspect the three rewritten claims (`N_01`, `B_01`, `AN_01`). Are the rewrites scientifically fair, too weak, or too strong?
4. Explain why the residual falls from `3.0` to `1.08`. What remains unresolved?
5. Identify which edges should be audited against original PDFs first.
6. Decide whether the six ideas should remain separate or whether any should merge/split.
7. Identify the best next experiment, simulation, or theorem needed to test the Atlas claim.
8. Explain what would falsify or seriously weaken the Atlas reading.

## Suggested Output Format

When responding, produce:

1. One-paragraph executive summary.
2. A per-idea interpretation, with claim/evidence IDs.
3. A section called "Most Important Tensions".
4. A section called "What Needs Source Verification".
5. A section called "Next Research Moves".
6. A section called "Possible Revisions To The Constellation".

Do not just summarize. Investigate. Push on the map. Tell us where the constellation is insightful, where it is fragile, and where it needs better extraction or better physics.

## Known Limitations

This constellation is currently a deterministic seeded graph, not a fully automated deep reading of all PDFs. Treat the claim and evidence labels as an index into the papers. Before using this as scientific authority:

- Verify source spans in the PDFs.
- Replace scalar placeholder observables with typed quantities where possible.
- Confirm whether each edge is a fair prediction relation.
- Audit whether `in_regime` and `out_of_regime` tags are physically justified.
- Revisit the three claim rewrites with domain expertise.

The map is useful because it makes tensions explicit. It is not useful if treated as final truth.
