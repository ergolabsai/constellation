# Constellation Report

- Papers: 21
- Claims: 30
- Evidence pieces: 25
- Claim-evidence edges: 151 (88 from semantic cross-paper propagation)
- Cost model: `stature_weighted_situate` (incoming paper(s): `atlas2026`)
- Initial residual: 26.157
- Final residual: 6.157
- Claim rewrite distance: 4.000

## Rewrites

- `A_01`: `[1.0, 1.0]` -> `[1.0, 0.0]`; residual 5.000 -> 0.000; lambda=0.30
- `A_04`: `[1.0, 1.0]` -> `[1.0, 0.0]`; residual 5.000 -> 0.000; lambda=0.30
- `A_06`: `[1.0, 1.0]` -> `[1.0, 0.0]`; residual 5.000 -> 0.000; lambda=0.30
- `A_07`: `[1.0, 1.0]` -> `[1.0, 0.0]`; residual 5.000 -> 0.000; lambda=0.30

## Map state

- Highest stature claims (independent backing papers): `A_05` (7), `GK_02` (6), `N_01` (6), `N_02` (6), `AN_01` (5), `AN_02` (5), `BR_01` (5), `B_01` (5)
- Implicit-headline claims (propagation contradicts comparable evidence; structural suspects): `A_01`, `A_04`, `A_06`, `A_07`
- Consensus-aligned claims (propagation agrees with the rest of the field): `AN_01`, `AN_02`, `A_02`, `A_03`, `A_05`, `BR_01`, `B_01`, `CK_01`, `CL_01`, `CR_01`, `FR_01`, `GK_01`, `GK_02`, `H_02`, `MY_01`, `N_01`, `N_02`, `S_01`, `S_02`, `Z_01`

## Subjects

### Beltrami / double-Beltrami equilibrium constructions

_Evidence about the existence, beta, and structure of Beltrami / double-Beltrami equilibria that admit the H3 quartic Alfven minimum._

_2 established · 0 contested · 2 novel_

**Idea 1 [NOVEL]: atlas2026 (A_02, A_03): H3 quartic Alfven minimum is the structural ingredient absent from shear-flow-only treatments**
- Papers: `atlas2026`  ·  Claims: `A_02`, `A_03`
- Scope.keywords: atlas, h3, rigid-beltrami
- Supporting evidence: `ev_atlas_h3_value`
- Supported by: `atlas2026`, `mahajan1998`
- Next steps:
  - **experiment** — Independent replication: Ask a different group to reproduce the supporting measurement(s) inside Beltrami / double-Beltrami equilibrium constructions using their own pipeline. The map will record the new contributor as independent evidence and promote this idea toward established.
  - **simulation** — Probe the scope boundary: Sweep the parameters at the edge of the claimed scope and look for the threshold where the predicted outcome flips. This either ratifies a new causal state or absorbs this idea into an existing one.

**Idea 2 [NOVEL]: atlas2026 (A_07): RIGID-BELTRAMI-A double-Beltrami equilibrium achieves beta=12.3% with all H1-H5 satisfied**
- Papers: `atlas2026`  ·  Claims: `A_07` [implicit-headline]
- Scope.keywords: atlas, h3, rigid-beltrami
- Supporting evidence: `ev_atlas_h3_value`, `ev_chandra_ck`, `ev_mahajan_db`
- Supported by: `atlas2026`, `chandrasekhar1957`, `mahajan1998`
- Next steps:
  - **experiment** — Independent replication: Ask a different group to reproduce the supporting measurement(s) inside Beltrami / double-Beltrami equilibrium constructions using their own pipeline. The map will record the new contributor as independent evidence and promote this idea toward established.
  - **simulation** — Probe the scope boundary: Sweep the parameters at the edge of the claimed scope and look for the threshold where the predicted outcome flips. This either ratifies a new causal state or absorbs this idea into an existing one.

**Idea 3 [ESTABLISHED]: chandrasekhar1957 (CK_01): Force-free curl H = alpha H fields admit poloidal and toroidal eigenfunction solutions**
- Papers: `chandrasekhar1957`  ·  Claims: `CK_01`
- Scope.keywords: chandrasekhar1957
- Supporting evidence: `ev_chandra_ck`
- Supported by: `atlas2026`
- Next steps:
  - **experiment** — Counter-experiment proposal: Identify a measurement that, if it landed at a value contrary to this idea's prediction within Beltrami / double-Beltrami equilibrium constructions, would force a rewrite. Document what such a measurement would look like and which device could perform it.
  - **theory** — Foundational assumption review: Walk the chain of assumptions that this idea rests on. Mark any that have NOT been directly tested in their own right -- those are the soft spots where a future counter-experiment could surface.
  - **simulation** — Adjacent-regime extrapolation: Sweep into the boundary of this idea's claimed scope and report where its predictions become unreliable. The result is a refined scope description; it may also surface a new candidate subject the registry does not yet cover.

**Idea 4 [ESTABLISHED]: mahajan1998 (MY_01): Coupled magnetofluid admits two-parameter double-Beltrami equilibria with non-trivial flow and pressure**
- Papers: `mahajan1998`  ·  Claims: `MY_01`
- Scope.keywords: mahajan1998
- Supporting evidence: `ev_atlas_h3_value`, `ev_mahajan_db`
- Supported by: `atlas2026`
- Next steps:
  - **experiment** — Counter-experiment proposal: Identify a measurement that, if it landed at a value contrary to this idea's prediction within Beltrami / double-Beltrami equilibrium constructions, would force a rewrite. Document what such a measurement would look like and which device could perform it.
  - **theory** — Foundational assumption review: Walk the chain of assumptions that this idea rests on. Mark any that have NOT been directly tested in their own right -- those are the soft spots where a future counter-experiment could surface.
  - **simulation** — Adjacent-regime extrapolation: Sweep into the boundary of this idea's claimed scope and report where its predictions become unreliable. The result is a refined scope description; it may also surface a new candidate subject the registry does not yet cover.

### Continuum spectrum near the Alfven minimum

_Evidence about the structure of the Alfven continuum near its quartic minimum (Friman-Rotenberg, Hameiri-Lust-Hameiri operators) and the discrete spectrum accumulating there._

_3 established · 0 contested · 1 novel_

**Idea 1 [NOVEL]: atlas2026 (A_04): Bi-orthogonal Picone identity generalizes Newcomb node-counting to non-self-adjoint operators**
- Papers: `atlas2026`  ·  Claims: `A_04` [implicit-headline]
- Scope.keywords: atlas, h3, rigid-beltrami
- Supporting evidence: `ev_friman_overstable`, `ev_hameiri_continuum`
- Supported by: `frieman1960`, `hameiri1981`, `hameiri1985`
- Next steps:
  - **experiment** — Independent replication: Ask a different group to reproduce the supporting measurement(s) inside Continuum spectrum near the Alfven minimum using their own pipeline. The map will record the new contributor as independent evidence and promote this idea toward established.
  - **simulation** — Probe the scope boundary: Sweep the parameters at the edge of the claimed scope and look for the threshold where the predicted outcome flips. This either ratifies a new causal state or absorbs this idea into an existing one.

**Idea 2 [ESTABLISHED]: frieman1960 (FR_01): Linear MHD stability with stationary flow is governed by a non-Hermitian operator**
- Papers: `frieman1960`  ·  Claims: `FR_01`
- Scope.keywords: frieman1960
- Supporting evidence: `ev_friman_overstable`
- Supported by: `atlas2026`
- Next steps:
  - **experiment** — Counter-experiment proposal: Identify a measurement that, if it landed at a value contrary to this idea's prediction within Continuum spectrum near the Alfven minimum, would force a rewrite. Document what such a measurement would look like and which device could perform it.
  - **theory** — Foundational assumption review: Walk the chain of assumptions that this idea rests on. Mark any that have NOT been directly tested in their own right -- those are the soft spots where a future counter-experiment could surface.
  - **simulation** — Adjacent-regime extrapolation: Sweep into the boundary of this idea's claimed scope and report where its predictions become unreliable. The result is a refined scope description; it may also surface a new candidate subject the registry does not yet cover.

**Idea 3 [ESTABLISHED]: hameiri1981 (H_01): Sufficient stability conditions for rotating screw-pinch follow from circle theorems and spectral bounds**
- Papers: `hameiri1981`  ·  Claims: `H_01`
- Scope.keywords: hameiri1981
- Supporting evidence: `ev_hameiri_continuum`
- Supported by: `atlas2026`, `hameiri1985`
- Next steps:
  - **experiment** — Counter-experiment proposal: Identify a measurement that, if it landed at a value contrary to this idea's prediction within Continuum spectrum near the Alfven minimum, would force a rewrite. Document what such a measurement would look like and which device could perform it.
  - **theory** — Foundational assumption review: Walk the chain of assumptions that this idea rests on. Mark any that have NOT been directly tested in their own right -- those are the soft spots where a future counter-experiment could surface.
  - **simulation** — Adjacent-regime extrapolation: Sweep into the boundary of this idea's claimed scope and report where its predictions become unreliable. The result is a refined scope description; it may also surface a new candidate subject the registry does not yet cover.

**Idea 4 [ESTABLISHED]: hameiri1985 (H_02): Essential spectrum of ideal MHD with flow consists of Doppler-shifted Alfven and slow continua**
- Papers: `hameiri1985`  ·  Claims: `H_02`
- Scope.keywords: hameiri1985
- Supporting evidence: `ev_hameiri_continuum`
- Supported by: `atlas2026`, `hameiri1981`
- Next steps:
  - **experiment** — Counter-experiment proposal: Identify a measurement that, if it landed at a value contrary to this idea's prediction within Continuum spectrum near the Alfven minimum, would force a rewrite. Document what such a measurement would look like and which device could perform it.
  - **theory** — Foundational assumption review: Walk the chain of assumptions that this idea rests on. Mark any that have NOT been directly tested in their own right -- those are the soft spots where a future counter-experiment could surface.
  - **simulation** — Adjacent-regime extrapolation: Sweep into the boundary of this idea's claimed scope and report where its predictions become unreliable. The result is a refined scope description; it may also surface a new candidate subject the registry does not yet cover.

### m=0 sausage growth and shear-flow stabilization

_Evidence about m=0 sausage instability scaling, sheared-flow stabilization thresholds, and downstream confinement outcomes in Z-pinches._

_5 established · 0 contested · 0 novel_

**Idea 1 [ESTABLISHED]: zhang2019 (Z_01): FuZE experimentally demonstrates sustained microsecond-scale neutron production during a quiescent period**
- Papers: `zhang2019`  ·  Claims: `Z_01`
- Scope.keywords: zhang2019
- Supporting evidence: `ev_zhang_neutrons`
- Next steps:
  - **experiment** — Counter-experiment proposal: Identify a measurement that, if it landed at a value contrary to this idea's prediction within m=0 sausage growth and shear-flow stabilization, would force a rewrite. Document what such a measurement would look like and which device could perform it.
  - **theory** — Foundational assumption review: Walk the chain of assumptions that this idea rests on. Mark any that have NOT been directly tested in their own right -- those are the soft spots where a future counter-experiment could surface.
  - **simulation** — Adjacent-regime extrapolation: Sweep into the boundary of this idea's claimed scope and report where its predictions become unreliable. The result is a refined scope description; it may also surface a new candidate subject the registry does not yet cover.

**Idea 2 [ESTABLISHED]: crews2024 (CR_01): Kadomtsev interchange criterion has an entropy-gradient interpretation analogous to Schwarzschild-Ledoux**
- Papers: `crews2024`  ·  Claims: `CR_01`
- Scope.keywords: crews2024
- Supporting evidence: `ev_crews_entropy`, `ev_shumlak_threshold`
- Supported by: `shumlak1995`
- Next steps:
  - **experiment** — Counter-experiment proposal: Identify a measurement that, if it landed at a value contrary to this idea's prediction within m=0 sausage growth and shear-flow stabilization, would force a rewrite. Document what such a measurement would look like and which device could perform it.
  - **theory** — Foundational assumption review: Walk the chain of assumptions that this idea rests on. Mark any that have NOT been directly tested in their own right -- those are the soft spots where a future counter-experiment could surface.
  - **simulation** — Adjacent-regime extrapolation: Sweep into the boundary of this idea's claimed scope and report where its predictions become unreliable. The result is a refined scope description; it may also surface a new candidate subject the registry does not yet cover.

**Idea 3 [ESTABLISHED]: angus2020 (AN_02): Required shear for m=0 stabilization scales with profile-dependent shear-free growth; m=1 needs a different mechanism**
- Papers: `angus2020`  ·  Claims: `AN_02`
- Scope.keywords: angus, profile, shear
- Supporting evidence: `ev_angus_m0_scaling`
- Supported by: `shumlak1995`
- Next steps:
  - **experiment** — Counter-experiment proposal: Identify a measurement that, if it landed at a value contrary to this idea's prediction within m=0 sausage growth and shear-flow stabilization, would force a rewrite. Document what such a measurement would look like and which device could perform it.
  - **theory** — Foundational assumption review: Walk the chain of assumptions that this idea rests on. Mark any that have NOT been directly tested in their own right -- those are the soft spots where a future counter-experiment could surface.
  - **simulation** — Adjacent-regime extrapolation: Sweep into the boundary of this idea's claimed scope and report where its predictions become unreliable. The result is a refined scope description; it may also surface a new candidate subject the registry does not yet cover.

**Idea 4 [ESTABLISHED]: shumlak1995 (S_01): Sheared axial flow v'/(kV_A) above about 0.1 stabilizes the m=0 sausage mode in static Z-pinch**
- Papers: `shumlak1995`  ·  Claims: `S_01`
- Scope.keywords: m=0, shear, shumlak
- Supporting evidence: `ev_angus_m0_scaling`, `ev_shumlak_threshold`
- Supported by: `angus2020`, `crews2024`
- Next steps:
  - **experiment** — Counter-experiment proposal: Identify a measurement that, if it landed at a value contrary to this idea's prediction within m=0 sausage growth and shear-flow stabilization, would force a rewrite. Document what such a measurement would look like and which device could perform it.
  - **theory** — Foundational assumption review: Walk the chain of assumptions that this idea rests on. Mark any that have NOT been directly tested in their own right -- those are the soft spots where a future counter-experiment could surface.
  - **simulation** — Adjacent-regime extrapolation: Sweep into the boundary of this idea's claimed scope and report where its predictions become unreliable. The result is a refined scope description; it may also surface a new candidate subject the registry does not yet cover.

**Idea 5 [ESTABLISHED]: shumlak2001 (S_02): ZaP experiment observes a long stable period coincident with sheared sub-Alfvenic flow**
- Papers: `shumlak2001`  ·  Claims: `S_02`
- Scope.keywords: quiescent, shear, zap
- Supporting evidence: `ev_shumlak_zap`
- Next steps:
  - **experiment** — Counter-experiment proposal: Identify a measurement that, if it landed at a value contrary to this idea's prediction within m=0 sausage growth and shear-flow stabilization, would force a rewrite. Document what such a measurement would look like and which device could perform it.
  - **theory** — Foundational assumption review: Walk the chain of assumptions that this idea rests on. Mark any that have NOT been directly tested in their own right -- those are the soft spots where a future counter-experiment could surface.
  - **simulation** — Adjacent-regime extrapolation: Sweep into the boundary of this idea's claimed scope and report where its predictions become unreliable. The result is a refined scope description; it may also surface a new candidate subject the registry does not yet cover.

### m=1 kink stability in helical / rotating Z-pinches

_Evidence reporting whether the m=1 kink mode is stable in helical or rotating Z-pinch settings at moderate Mach-Alfven number. Value 1 = stable, 0 = unstable / persists._

_5 established · 7 contested · 2 novel_

**Idea 1 [NOVEL]: atlas2026 (A_02): H3 quartic Alfven minimum is the structural ingredient absent from shear-flow-only treatments**
- Papers: `atlas2026`  ·  Claims: `A_02`
- Scope.keywords: atlas, h3, rigid-beltrami
- Supporting evidence: `ev_angus_m1_persists`
- Supported by: `angus2020`, `atlas2026`
- Next steps:
  - **experiment** — Independent replication: Ask a different group to reproduce the supporting measurement(s) inside m=1 kink stability in helical / rotating Z-pinches using their own pipeline. The map will record the new contributor as independent evidence and promote this idea toward established.
  - **simulation** — Probe the scope boundary: Sweep the parameters at the edge of the claimed scope and look for the threshold where the predicted outcome flips. This either ratifies a new causal state or absorbs this idea into an existing one.

**Idea 2 [NOVEL]: atlas2026 (A_05): Below SARI bound M_A<1, ideal-MHD m=1 growth rate is zero in the asymptotic d_i/R -> 0 regime**
- Papers: `atlas2026`  ·  Claims: `A_05`
- Scope.keywords: atlas, h3, rigid-beltrami
- Supporting evidence: `ev_angus_m1_persists`, `ev_atlas_kink_zero`, `ev_bondeson_toroidal`, `ev_brughmans_growth`, `ev_goedbloed_sari`, `ev_newcomb_static`
- Contests: `idea_m1_stability_outcome_009` (angus2020) at `ev_atlas_kink_zero`; `idea_m1_stability_outcome_010` (bondeson1989) at `ev_atlas_kink_zero`; `idea_m1_stability_outcome_012` (newcomb1960) at `ev_atlas_kink_zero`
- Supported by: `atlas2026`, `brughmans2024`, `claes2020`, `goedbloed2022`, `hameiri1985`, `newcomb1960`, `sainterme2026`, `shiraishi2005`
- Next steps:
  - **literature** — Reconcile with contested ideas: This novel idea contradicts 3 existing idea(s) at shared evidence. Identify the parameter that separates the contesting scopes (e.g., in the m=1 case, what about Atlas's H1-H5 regime is structurally different from prior rotating-Z-pinch setups?).
  - **experiment** — Independent replication: Ask a different group to reproduce the supporting measurement(s) inside m=1 kink stability in helical / rotating Z-pinches using their own pipeline. The map will record the new contributor as independent evidence and promote this idea toward established.
  - **simulation** — Probe the scope boundary: Sweep the parameters at the edge of the claimed scope and look for the threshold where the predicted outcome flips. This either ratifies a new causal state or absorbs this idea into an existing one.

**Idea 3 [CONTESTED]: sainterme2026 (SE_01): In the Hall regime, global whistler instabilities grow significantly faster than ideal-MHD modes**
- Papers: `sainterme2026`  ·  Claims: `SE_01`
- Scope.keywords: hall, whistler
- Supporting evidence: `ev_atlas_kink_zero`
- Contests: `idea_m1_stability_outcome_009` (angus2020) at `ev_atlas_kink_zero`; `idea_m1_stability_outcome_010` (bondeson1989) at `ev_atlas_kink_zero`; `idea_m1_stability_outcome_012` (newcomb1960) at `ev_atlas_kink_zero`
- Supported by: `atlas2026`, `goedbloed2022`, `shiraishi2005`
- Next steps:
  - **theory** — Identify the scope-flipping parameter: Compare this idea's home scope against 3 contesting idea(s) and isolate the parameter(s) whose value separates the outcomes. The interrogation question for m=1 kink stability in helical / rotating Z-pinches lives here.
  - **simulation** — Controlled scope-overlap sweep: Run a parameter sweep that crosses from this idea's regime into the contesting idea's regime, holding everything else constant, and identify the transition point where the outcome flips.
  - **literature** — Audit the contesting idea's assumptions: For each contesting idea, identify which structural assumption it makes that this idea does not (or vice versa). Decide whether the disagreement is a genuine physical split or a scope-labelling artifact.

**Idea 4 [CONTESTED]: atlas2026 (A_01, A_04, A_06, A_07): 5 constraints H1-H5 are necessary and sufficient for m=1 stability in rotating helical Z-pinch**
- Papers: `atlas2026`  ·  Claims: `A_01` [implicit-headline], `A_04` [implicit-headline], `A_06` [implicit-headline], `A_07` [implicit-headline]
- Scope.keywords: atlas, h3, rigid-beltrami
- Supporting evidence: `ev_atlas_kink_zero`
- Contests: `idea_m1_stability_outcome_009` (angus2020) at `ev_atlas_kink_zero`; `idea_m1_stability_outcome_010` (bondeson1989) at `ev_atlas_kink_zero`; `idea_m1_stability_outcome_012` (newcomb1960) at `ev_atlas_kink_zero`
- Supported by: `atlas2026`, `goedbloed2022`, `sainterme2026`, `shiraishi2005`
- Next steps:
  - **theory** — Identify the scope-flipping parameter: Compare this idea's home scope against 3 contesting idea(s) and isolate the parameter(s) whose value separates the outcomes. The interrogation question for m=1 kink stability in helical / rotating Z-pinches lives here.
  - **simulation** — Controlled scope-overlap sweep: Run a parameter sweep that crosses from this idea's regime into the contesting idea's regime, holding everything else constant, and identify the transition point where the outcome flips.
  - **literature** — Audit the contesting idea's assumptions: For each contesting idea, identify which structural assumption it makes that this idea does not (or vice versa). Decide whether the disagreement is a genuine physical split or a scope-labelling artifact.

**Idea 5 [CONTESTED]: goedbloed2022 (GK_02): At M_A >= 1 continuum overlap opens uncontrolled SARI spectrum**
- Papers: `goedbloed2022`  ·  Claims: `GK_02`
- Scope.keywords: alfven, ma, sari
- Supporting evidence: `ev_atlas_kink_zero`, `ev_goedbloed_sari`
- Contests: `idea_m1_stability_outcome_009` (angus2020) at `ev_atlas_kink_zero`; `idea_m1_stability_outcome_010` (bondeson1989) at `ev_atlas_kink_zero`; `idea_m1_stability_outcome_012` (newcomb1960) at `ev_atlas_kink_zero`
- Supported by: `atlas2026`, `brughmans2024`, `goedbloed2022`, `hameiri1985`, `sainterme2026`, `shiraishi2005`
- Next steps:
  - **theory** — Identify the scope-flipping parameter: Compare this idea's home scope against 3 contesting idea(s) and isolate the parameter(s) whose value separates the outcomes. The interrogation question for m=1 kink stability in helical / rotating Z-pinches lives here.
  - **simulation** — Controlled scope-overlap sweep: Run a parameter sweep that crosses from this idea's regime into the contesting idea's regime, holding everything else constant, and identify the transition point where the outcome flips.
  - **literature** — Audit the contesting idea's assumptions: For each contesting idea, identify which structural assumption it makes that this idea does not (or vice versa). Decide whether the disagreement is a genuine physical split or a scope-labelling artifact.

**Idea 6 [CONTESTED]: angus2020 (AN_01): Linear shear flow alone does not stabilize m=1 kink across realistic Z-pinch profile classes**
- Papers: `angus2020`  ·  Claims: `AN_01`
- Scope.keywords: angus, profile, shear
- Supporting evidence: `ev_angus_m1_persists`
- Contesting evidence: `ev_atlas_kink_zero`
- Contests: `idea_m1_stability_outcome_003` (sainterme2026) at `ev_atlas_kink_zero`; `idea_m1_stability_outcome_004` (atlas2026) at `ev_atlas_kink_zero`; `idea_m1_stability_outcome_006` (atlas2026) at `ev_atlas_kink_zero`; `idea_m1_stability_outcome_008` (goedbloed2022) at `ev_atlas_kink_zero`; `idea_m1_stability_outcome_014` (shiraishi2005) at `ev_atlas_kink_zero`
- Supported by: `atlas2026`, `bondeson1989`, `newcomb1960`
- Next steps:
  - **theory** — Identify the scope-flipping parameter: Compare this idea's home scope against 5 contesting idea(s) and isolate the parameter(s) whose value separates the outcomes. The interrogation question for m=1 kink stability in helical / rotating Z-pinches lives here.
  - **simulation** — Controlled scope-overlap sweep: Run a parameter sweep that crosses from this idea's regime into the contesting idea's regime, holding everything else constant, and identify the transition point where the outcome flips.
  - **literature** — Audit the contesting idea's assumptions: For each contesting idea, identify which structural assumption it makes that this idea does not (or vice versa). Decide whether the disagreement is a genuine physical split or a scope-labelling artifact.

**Idea 7 [CONTESTED]: bondeson1989 (B_01): In toroidal or cylindrical geometry, rotation mitigates but does not eliminate kink at finite pressure**
- Papers: `bondeson1989`  ·  Claims: `B_01`
- Scope.keywords: bondeson1989
- Supporting evidence: `ev_bondeson_toroidal`
- Contesting evidence: `ev_atlas_kink_zero`
- Contests: `idea_m1_stability_outcome_003` (sainterme2026) at `ev_atlas_kink_zero`; `idea_m1_stability_outcome_004` (atlas2026) at `ev_atlas_kink_zero`; `idea_m1_stability_outcome_006` (atlas2026) at `ev_atlas_kink_zero`; `idea_m1_stability_outcome_008` (goedbloed2022) at `ev_atlas_kink_zero`; `idea_m1_stability_outcome_014` (shiraishi2005) at `ev_atlas_kink_zero`
- Supported by: `angus2020`, `newcomb1960`
- Next steps:
  - **theory** — Identify the scope-flipping parameter: Compare this idea's home scope against 5 contesting idea(s) and isolate the parameter(s) whose value separates the outcomes. The interrogation question for m=1 kink stability in helical / rotating Z-pinches lives here.
  - **simulation** — Controlled scope-overlap sweep: Run a parameter sweep that crosses from this idea's regime into the contesting idea's regime, holding everything else constant, and identify the transition point where the outcome flips.
  - **literature** — Audit the contesting idea's assumptions: For each contesting idea, identify which structural assumption it makes that this idea does not (or vice versa). Decide whether the disagreement is a genuine physical split or a scope-labelling artifact.

**Idea 8 [CONTESTED]: newcomb1960 (N_01): Static Z-pinch at finite pressure cannot be linearly stable to m=1 in ideal MHD**
- Papers: `newcomb1960`  ·  Claims: `N_01`
- Scope.keywords: newcomb, static
- Supporting evidence: `ev_newcomb_static`
- Contesting evidence: `ev_atlas_kink_zero`
- Contests: `idea_m1_stability_outcome_003` (sainterme2026) at `ev_atlas_kink_zero`; `idea_m1_stability_outcome_004` (atlas2026) at `ev_atlas_kink_zero`; `idea_m1_stability_outcome_006` (atlas2026) at `ev_atlas_kink_zero`; `idea_m1_stability_outcome_008` (goedbloed2022) at `ev_atlas_kink_zero`; `idea_m1_stability_outcome_014` (shiraishi2005) at `ev_atlas_kink_zero`
- Supported by: `angus2020`, `bondeson1989`, `newcomb1960`
- Next steps:
  - **theory** — Identify the scope-flipping parameter: Compare this idea's home scope against 5 contesting idea(s) and isolate the parameter(s) whose value separates the outcomes. The interrogation question for m=1 kink stability in helical / rotating Z-pinches lives here.
  - **simulation** — Controlled scope-overlap sweep: Run a parameter sweep that crosses from this idea's regime into the contesting idea's regime, holding everything else constant, and identify the transition point where the outcome flips.
  - **literature** — Audit the contesting idea's assumptions: For each contesting idea, identify which structural assumption it makes that this idea does not (or vice versa). Decide whether the disagreement is a genuine physical split or a scope-labelling artifact.

**Idea 9 [CONTESTED]: shiraishi2005 (SH_01): Hall effect regularizes the Alfven singularity over a layer of thickness about d_i**
- Papers: `shiraishi2005`  ·  Claims: `SH_01`
- Scope.keywords: di, hall
- Supporting evidence: `ev_atlas_kink_zero`
- Contests: `idea_m1_stability_outcome_009` (angus2020) at `ev_atlas_kink_zero`; `idea_m1_stability_outcome_010` (bondeson1989) at `ev_atlas_kink_zero`; `idea_m1_stability_outcome_012` (newcomb1960) at `ev_atlas_kink_zero`
- Supported by: `atlas2026`, `goedbloed2022`, `sainterme2026`
- Next steps:
  - **theory** — Identify the scope-flipping parameter: Compare this idea's home scope against 3 contesting idea(s) and isolate the parameter(s) whose value separates the outcomes. The interrogation question for m=1 kink stability in helical / rotating Z-pinches lives here.
  - **simulation** — Controlled scope-overlap sweep: Run a parameter sweep that crosses from this idea's regime into the contesting idea's regime, holding everything else constant, and identify the transition point where the outcome flips.
  - **literature** — Audit the contesting idea's assumptions: For each contesting idea, identify which structural assumption it makes that this idea does not (or vice versa). Decide whether the disagreement is a genuine physical split or a scope-labelling artifact.

**Idea 10 [ESTABLISHED]: claes2020 (CL_01): Legolas finite-element MHD spectroscopy computes the full eigenspectrum for 1D equilibria with flow**
- Papers: `claes2020`  ·  Claims: `CL_01`
- Scope.keywords: claes2020
- Supporting evidence: `ev_brughmans_growth`
- Supported by: `atlas2026`, `brughmans2024`
- Next steps:
  - **experiment** — Counter-experiment proposal: Identify a measurement that, if it landed at a value contrary to this idea's prediction within m=1 kink stability in helical / rotating Z-pinches, would force a rewrite. Document what such a measurement would look like and which device could perform it.
  - **theory** — Foundational assumption review: Walk the chain of assumptions that this idea rests on. Mark any that have NOT been directly tested in their own right -- those are the soft spots where a future counter-experiment could surface.
  - **simulation** — Adjacent-regime extrapolation: Sweep into the boundary of this idea's claimed scope and report where its predictions become unreliable. The result is a refined scope description; it may also surface a new candidate subject the registry does not yet cover.

**Idea 11 [ESTABLISHED]: brughmans2024 (BR_01): Non-axisymmetric SARI modes are confirmed numerically by Legolas with growth rates comparable to MRI**
- Papers: `brughmans2024`  ·  Claims: `BR_01`
- Scope.keywords: legolas, sari
- Supporting evidence: `ev_brughmans_growth`, `ev_goedbloed_sari`
- Supported by: `atlas2026`, `claes2020`, `goedbloed2022`, `hameiri1985`
- Next steps:
  - **experiment** — Counter-experiment proposal: Identify a measurement that, if it landed at a value contrary to this idea's prediction within m=1 kink stability in helical / rotating Z-pinches, would force a rewrite. Document what such a measurement would look like and which device could perform it.
  - **theory** — Foundational assumption review: Walk the chain of assumptions that this idea rests on. Mark any that have NOT been directly tested in their own right -- those are the soft spots where a future counter-experiment could surface.
  - **simulation** — Adjacent-regime extrapolation: Sweep into the boundary of this idea's claimed scope and report where its predictions become unreliable. The result is a refined scope description; it may also surface a new candidate subject the registry does not yet cover.

**Idea 12 [ESTABLISHED]: goedbloed2022 (GK_01): Super-Alfvenic Rotational Instability emerges from overlap of Doppler-shifted Alfven continua**
- Papers: `goedbloed2022`  ·  Claims: `GK_01`
- Scope.keywords: alfven, ma, sari
- Supporting evidence: `ev_goedbloed_sari`
- Supported by: `atlas2026`, `brughmans2024`, `goedbloed2022`, `hameiri1985`
- Next steps:
  - **experiment** — Counter-experiment proposal: Identify a measurement that, if it landed at a value contrary to this idea's prediction within m=1 kink stability in helical / rotating Z-pinches, would force a rewrite. Document what such a measurement would look like and which device could perform it.
  - **theory** — Foundational assumption review: Walk the chain of assumptions that this idea rests on. Mark any that have NOT been directly tested in their own right -- those are the soft spots where a future counter-experiment could surface.
  - **simulation** — Adjacent-regime extrapolation: Sweep into the boundary of this idea's claimed scope and report where its predictions become unreliable. The result is a refined scope description; it may also surface a new candidate subject the registry does not yet cover.

**Idea 13 [ESTABLISHED]: hameiri1985 (H_02): Essential spectrum of ideal MHD with flow consists of Doppler-shifted Alfven and slow continua**
- Papers: `hameiri1985`  ·  Claims: `H_02`
- Scope.keywords: hameiri1985
- Supporting evidence: `ev_goedbloed_sari`
- Supported by: `atlas2026`, `brughmans2024`, `goedbloed2022`
- Next steps:
  - **experiment** — Counter-experiment proposal: Identify a measurement that, if it landed at a value contrary to this idea's prediction within m=1 kink stability in helical / rotating Z-pinches, would force a rewrite. Document what such a measurement would look like and which device could perform it.
  - **theory** — Foundational assumption review: Walk the chain of assumptions that this idea rests on. Mark any that have NOT been directly tested in their own right -- those are the soft spots where a future counter-experiment could surface.
  - **simulation** — Adjacent-regime extrapolation: Sweep into the boundary of this idea's claimed scope and report where its predictions become unreliable. The result is a refined scope description; it may also surface a new candidate subject the registry does not yet cover.

**Idea 14 [ESTABLISHED]: newcomb1960 (N_02): Number of unstable eigenvalues equals number of interior nodes of the marginal mode**
- Papers: `newcomb1960`  ·  Claims: `N_02`
- Scope.keywords: newcomb, static
- Supporting evidence: `ev_newcomb_static`
- Supported by: `atlas2026`, `newcomb1960`
- Next steps:
  - **experiment** — Counter-experiment proposal: Identify a measurement that, if it landed at a value contrary to this idea's prediction within m=1 kink stability in helical / rotating Z-pinches, would force a rewrite. Document what such a measurement would look like and which device could perform it.
  - **theory** — Foundational assumption review: Walk the chain of assumptions that this idea rests on. Mark any that have NOT been directly tested in their own right -- those are the soft spots where a future counter-experiment could surface.
  - **simulation** — Adjacent-regime extrapolation: Sweep into the boundary of this idea's claimed scope and report where its predictions become unreliable. The result is a refined scope description; it may also surface a new candidate subject the registry does not yet cover.

### Numerical eigenvalue benchmarks and constraint-violation tests

_Evidence from code-to-code MHD eigenvalue benchmarks and from violating Kumar's H1-H5 constraints to see the framework break in the predicted way._

_5 established · 0 contested · 2 novel_

**Idea 1 [NOVEL]: atlas2026 (A_01): 5 constraints H1-H5 are necessary and sufficient for m=1 stability in rotating helical Z-pinch**
- Papers: `atlas2026`  ·  Claims: `A_01` [implicit-headline]
- Scope.keywords: atlas, h3, rigid-beltrami
- Supporting evidence: `ev_atlas_120pts`
- Supported by: `atlas2026`
- Next steps:
  - **experiment** — Independent replication: Ask a different group to reproduce the supporting measurement(s) inside Numerical eigenvalue benchmarks and constraint-violation tests using their own pipeline. The map will record the new contributor as independent evidence and promote this idea toward established.
  - **simulation** — Probe the scope boundary: Sweep the parameters at the edge of the claimed scope and look for the threshold where the predicted outcome flips. This either ratifies a new causal state or absorbs this idea into an existing one.

**Idea 2 [NOVEL]: atlas2026 (A_05): Below SARI bound M_A<1, ideal-MHD m=1 growth rate is zero in the asymptotic d_i/R -> 0 regime**
- Papers: `atlas2026`  ·  Claims: `A_05`
- Scope.keywords: atlas, h3, rigid-beltrami
- Supporting evidence: `ev_atlas_120pts`, `ev_atlas_pseudospec`
- Supported by: `atlas2026`, `frieman1960`
- Next steps:
  - **experiment** — Independent replication: Ask a different group to reproduce the supporting measurement(s) inside Numerical eigenvalue benchmarks and constraint-violation tests using their own pipeline. The map will record the new contributor as independent evidence and promote this idea toward established.
  - **simulation** — Probe the scope boundary: Sweep the parameters at the edge of the claimed scope and look for the threshold where the predicted outcome flips. This either ratifies a new causal state or absorbs this idea into an existing one.

**Idea 3 [ESTABLISHED]: claes2020 (CL_01): Legolas finite-element MHD spectroscopy computes the full eigenspectrum for 1D equilibria with flow**
- Papers: `claes2020`  ·  Claims: `CL_01`
- Scope.keywords: claes2020
- Supporting evidence: `ev_legolas_bench`
- Supported by: `dejonghe2022`
- Next steps:
  - **experiment** — Counter-experiment proposal: Identify a measurement that, if it landed at a value contrary to this idea's prediction within Numerical eigenvalue benchmarks and constraint-violation tests, would force a rewrite. Document what such a measurement would look like and which device could perform it.
  - **theory** — Foundational assumption review: Walk the chain of assumptions that this idea rests on. Mark any that have NOT been directly tested in their own right -- those are the soft spots where a future counter-experiment could surface.
  - **simulation** — Adjacent-regime extrapolation: Sweep into the boundary of this idea's claimed scope and report where its predictions become unreliable. The result is a refined scope description; it may also surface a new candidate subject the registry does not yet cover.

**Idea 4 [ESTABLISHED]: dejonghe2022 (DJ_01): Legolas extension with viscosity and Hall current is benchmarked against historic results**
- Papers: `dejonghe2022`  ·  Claims: `DJ_01`
- Scope.keywords: dejonghe2022
- Supporting evidence: `ev_legolas_bench`
- Supported by: `claes2020`
- Next steps:
  - **experiment** — Counter-experiment proposal: Identify a measurement that, if it landed at a value contrary to this idea's prediction within Numerical eigenvalue benchmarks and constraint-violation tests, would force a rewrite. Document what such a measurement would look like and which device could perform it.
  - **theory** — Foundational assumption review: Walk the chain of assumptions that this idea rests on. Mark any that have NOT been directly tested in their own right -- those are the soft spots where a future counter-experiment could surface.
  - **simulation** — Adjacent-regime extrapolation: Sweep into the boundary of this idea's claimed scope and report where its predictions become unreliable. The result is a refined scope description; it may also surface a new candidate subject the registry does not yet cover.

**Idea 5 [ESTABLISHED]: atlas2026 (A_04): Bi-orthogonal Picone identity generalizes Newcomb node-counting to non-self-adjoint operators**
- Papers: `atlas2026`  ·  Claims: `A_04` [implicit-headline]
- Scope.keywords: atlas, h3, rigid-beltrami
- Supporting evidence: `ev_atlas_newcomb_bench`
- Supported by: `newcomb1960`
- Next steps:
  - **experiment** — Counter-experiment proposal: Identify a measurement that, if it landed at a value contrary to this idea's prediction within Numerical eigenvalue benchmarks and constraint-violation tests, would force a rewrite. Document what such a measurement would look like and which device could perform it.
  - **theory** — Foundational assumption review: Walk the chain of assumptions that this idea rests on. Mark any that have NOT been directly tested in their own right -- those are the soft spots where a future counter-experiment could surface.
  - **simulation** — Adjacent-regime extrapolation: Sweep into the boundary of this idea's claimed scope and report where its predictions become unreliable. The result is a refined scope description; it may also surface a new candidate subject the registry does not yet cover.

**Idea 6 [ESTABLISHED]: frieman1960 (FR_01): Linear MHD stability with stationary flow is governed by a non-Hermitian operator**
- Papers: `frieman1960`  ·  Claims: `FR_01`
- Scope.keywords: frieman1960
- Supporting evidence: `ev_atlas_pseudospec`
- Supported by: `atlas2026`
- Next steps:
  - **experiment** — Counter-experiment proposal: Identify a measurement that, if it landed at a value contrary to this idea's prediction within Numerical eigenvalue benchmarks and constraint-violation tests, would force a rewrite. Document what such a measurement would look like and which device could perform it.
  - **theory** — Foundational assumption review: Walk the chain of assumptions that this idea rests on. Mark any that have NOT been directly tested in their own right -- those are the soft spots where a future counter-experiment could surface.
  - **simulation** — Adjacent-regime extrapolation: Sweep into the boundary of this idea's claimed scope and report where its predictions become unreliable. The result is a refined scope description; it may also surface a new candidate subject the registry does not yet cover.

**Idea 7 [ESTABLISHED]: newcomb1960 (N_02): Number of unstable eigenvalues equals number of interior nodes of the marginal mode**
- Papers: `newcomb1960`  ·  Claims: `N_02`
- Scope.keywords: newcomb, static
- Supporting evidence: `ev_atlas_newcomb_bench`
- Supported by: `atlas2026`
- Next steps:
  - **experiment** — Counter-experiment proposal: Identify a measurement that, if it landed at a value contrary to this idea's prediction within Numerical eigenvalue benchmarks and constraint-violation tests, would force a rewrite. Document what such a measurement would look like and which device could perform it.
  - **theory** — Foundational assumption review: Walk the chain of assumptions that this idea rests on. Mark any that have NOT been directly tested in their own right -- those are the soft spots where a future counter-experiment could surface.
  - **simulation** — Adjacent-regime extrapolation: Sweep into the boundary of this idea's claimed scope and report where its predictions become unreliable. The result is a refined scope description; it may also surface a new candidate subject the registry does not yet cover.

### Ungrouped (no comparability group authored yet)

_Claims and evidence not covered by any comparability group. Add a group to the corpus's comparability.json to surface these as a first-class subject._

- _No ideas yet (ungrouped subject)._
- Evidence: `ev_atlas_h1_violate`, `ev_atlas_h3_violate`, `ev_sainterme_whistler`, `ev_shiraishi_dilayer`, `ev_wang_smri`
