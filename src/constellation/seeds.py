from __future__ import annotations

from pathlib import Path

from .util import Json, source_span


def extract_seeded_records(pdf_path: Path, text: str) -> tuple[Json, list[Json], list[Json]]:
    name = pdf_path.name.lower()
    atlas_seed = _atlas_seed(pdf_path, text)
    if atlas_seed:
        return atlas_seed
    if "shumlak2009" in name:
        return _shumlak2009(pdf_path, text)
    if "eigenmode" in name:
        return _angus2020(pdf_path, text)
    if "gyrokinetic" in name:
        return _geyko2019(pdf_path, text)
    return _fallback(pdf_path, text)


def _paper(
    paper_id: str,
    title: str,
    pdf_path: Path,
    text: str,
    *,
    year: int | None,
    authors: list[str],
) -> Json:
    return {
        "paper_id": paper_id,
        "title": title,
        "year": year,
        "authors": authors,
        "pdf_path": str(pdf_path),
        "provenance": {
            "extractor": "deterministic_seed",
            "confidence": 0.95,
            "review_status": "unreviewed",
            "source_span": source_span(text, title),
        },
    }


def _claim(
    claim_id: str,
    paper_id: str,
    label: str,
    *,
    home_regime: Json,
    strengths: list[str] | None = None,
    weaknesses: list[str],
    predictions: list[Json],
    source_span_text: str,
    confidence: float = 0.82,
) -> Json:
    return {
        "claim_id": claim_id,
        "paper_id": paper_id,
        "label": label,
        "stalk_basis": ["in_regime_strength", "out_regime_strength"],
        "x_init": [1.0, 1.0],
        "x_final": [1.0, 1.0],
        "home_regime": home_regime,
        "strengths": strengths or _default_claim_strengths(predictions),
        "weaknesses": weaknesses,
        "predictions": predictions,
        "rewrite_history": [],
        "provenance": {
            "extractor": "deterministic_seed",
            "confidence": confidence,
            "review_status": "unreviewed",
            "source_span": source_span_text,
        },
    }


def _default_claim_strengths(predictions: list[Json]) -> list[str]:
    if predictions:
        return [f"Makes {len(predictions)} explicit observable prediction(s) for sheaf comparison."]
    return ["Provides a scoped literature claim for review."]


def _evidence(
    evidence_id: str,
    paper_id: str,
    label: str,
    *,
    dimensions: list[Json],
    context: Json,
    source_span_text: str,
    confidence: float = 0.86,
) -> Json:
    return {
        "evidence_id": evidence_id,
        "paper_id": paper_id,
        "label": label,
        "core": {"dimensions": dimensions, "locked": True},
        "context": {
            "system": context.get("system", ""),
            "framework": context.get("framework", ""),
            "regime": context.get("regime", ""),
            "explicit_in_source": True,
            "filled_by_pipeline": False,
        },
        "provenance": {
            "extractor": "deterministic_seed",
            "confidence": confidence,
            "review_status": "unreviewed",
            "source_span": source_span_text,
        },
    }


def _pred(
    observable: str,
    value: float,
    *,
    scale: str = "normalized_binary",
    evidence_ids: list[str] | None = None,
    regime_tag: str | None = None,
) -> Json:
    pred = {"observable": observable, "value": value, "scale": scale}
    if evidence_ids:
        pred["evidence_ids"] = evidence_ids
    if regime_tag:
        pred["regime_tag"] = regime_tag
    return pred


def _dim(name: str, value: float, *, scale: str = "normalized_binary") -> Json:
    return {"name": name, "value": value, "scale": scale, "uncertainty": None}


def _shumlak2009(pdf_path: Path, text: str) -> tuple[Json, list[Json], list[Json]]:
    paper_id = "shumlak2009"
    paper = _paper(
        paper_id,
        "Equilibrium, flow shear and stability measurements in the Z-pinch",
        pdf_path,
        text,
        year=2009,
        authors=["U. Shumlak", "C. S. Adams", "J. M. Blakely"],
    )
    claims = [
        _claim(
            "S_01",
            paper_id,
            "ZaP plasmas show an extended quiescent period with low m=1 magnetic fluctuations coincident with sheared axial flow.",
            home_regime={
                "system": "ZaP flow Z-pinch experiment",
                "framework": "experiment",
                "regime_keywords": ["zap", "quiescent", "experimental"],
            },
            weaknesses=[
                "The paper reports coincidence between shear and stability, not a standalone causal proof.",
                "The measured flow shear is nonuniform rather than the uniform shear assumed by the threshold theory.",
            ],
            predictions=[_pred("m1_stabilized", 1.0)],
            source_span_text=source_span(text, "low magnetic fluctuations", "quiescent period"),
        ),
        _claim(
            "S_02",
            paper_id,
            "The 0.1 k V_A shear threshold is sufficient for m=1 stabilization in the Shumlak-Hartman linear ideal-MHD threshold model.",
            home_regime={
                "system": "flowing Z-pinch",
                "framework": "linear ideal MHD threshold model",
                "regime_keywords": ["zap", "uniform shear", "threshold"],
            },
            weaknesses=[
                "The original threshold assumes a specific uniform-shear ideal-MHD setup.",
                "The experiment does not by itself establish causality.",
                "Later profile-dependent eigenmode work tests regimes outside this threshold model.",
            ],
            predictions=[_pred("m1_stabilized", 1.0)],
            source_span_text=source_span(text, "0.1kVA", "threshold"),
        ),
        _claim(
            "S_03",
            paper_id,
            "Nonlinear simulations with nonuniform edge-localized flow shear show reduced m=0 instability compared with a static Z-pinch.",
            home_regime={
                "system": "flowing Z-pinch simulation",
                "framework": "resistive MHD simulation",
                "regime_keywords": ["simulation", "m = 0", "edge"],
            },
            weaknesses=[
                "The simulations focus on m=0 and do not provide a complete m=1 explanation.",
                "The computational setup is an idealized comparison to the experiment.",
            ],
            predictions=[_pred("m0_growth_reduced", 1.0)],
            source_span_text=source_span(text, "m = 0 mode", "nonuniform shear"),
        ),
    ]
    evidence = [
        _evidence(
            "ev_shumlak_zap_m1_low",
            paper_id,
            "Low m=1 fluctuation levels persist during the ZaP quiescent period when shear exceeds the theoretical threshold.",
            dimensions=[_dim("m1_stabilized", 1.0)],
            context={
                "system": "ZaP flow Z-pinch experiment",
                "framework": "experiment",
                "regime": "quiescent period with measured sheared axial flow",
            },
            source_span_text=source_span(text, "quiescent period", "m = 1"),
        ),
        _evidence(
            "ev_shumlak_m0_sim_reduced",
            paper_id,
            "Mach2 simulations show m=0 growth is reduced when axial flow shear is present.",
            dimensions=[_dim("m0_growth_reduced", 1.0)],
            context={
                "system": "flowing Z-pinch simulation",
                "framework": "resistive MHD simulation",
                "regime": "uniform and edge-localized shear comparisons",
            },
            source_span_text=source_span(text, "nonlinear computer simulations", "m = 0"),
        ),
    ]
    return paper, claims, evidence


def _angus2020(pdf_path: Path, text: str) -> tuple[Json, list[Json], list[Json]]:
    paper_id = "angus2020_eigenmode"
    paper = _paper(
        paper_id,
        "Eigenmode analysis of the sheared-flow Z-pinch",
        pdf_path,
        text,
        year=2020,
        authors=["J. R. Angus", "J. J. Van De Wetering", "M. Dorf", "V. I. Geyko"],
    )
    claims = [
        _claim(
            "A_01",
            paper_id,
            "Linear ideal-MHD eigenmode analysis does not explain observed long-lived m=1 stabilization for all tested profiles.",
            home_regime={
                "system": "flowing Z-pinch",
                "framework": "linear ideal MHD eigenmode analysis",
                "regime_keywords": ["linear ideal", "eigenmode", "fuze-like"],
            },
            weaknesses=[
                "The conclusion is scoped to linear ideal MHD, not all nonlinear or kinetic mechanisms.",
                "The profile families tested may still omit experimental effects.",
            ],
            predictions=[_pred("m1_stabilized", 0.0)],
            source_span_text=source_span(text, "not sufficient to provide linear stabilization", "m = 1"),
        ),
        _claim(
            "A_02",
            paper_id,
            "The m=0 shear threshold is profile dependent and scales with the shear-free growth-rate spectrum.",
            home_regime={
                "system": "flowing Z-pinch",
                "framework": "linear ideal MHD eigenmode analysis",
                "regime_keywords": ["m = 0", "profile", "growth rate"],
            },
            weaknesses=[
                "The threshold law is model-specific and should not be treated as a universal experimental rule.",
            ],
            predictions=[_pred("m0_threshold_profile_dependent", 1.0)],
            source_span_text=source_span(text, "m = 0 modes can be expressed", "growth rate"),
        ),
    ]
    evidence = [
        _evidence(
            "ev_angus_m1_not_stabilized",
            paper_id,
            "Even large imposed shear does not linearly stabilize m=1 kink modes for all tested profiles.",
            dimensions=[_dim("m1_stabilized", 0.0)],
            context={
                "system": "flowing Z-pinch",
                "framework": "linear ideal MHD eigenmode analysis",
                "regime": "Kadomtsev, Bennett, and FuZE-like profile families",
            },
            source_span_text=source_span(text, "not sufficient to provide linear stabilization", "m = 1"),
        ),
        _evidence(
            "ev_angus_m0_profile_threshold",
            paper_id,
            "m=0 stabilization thresholds vary strongly with the equilibrium pressure profile and shear-free growth rate.",
            dimensions=[_dim("m0_threshold_profile_dependent", 1.0)],
            context={
                "system": "flowing Z-pinch",
                "framework": "linear ideal MHD eigenmode analysis",
                "regime": "profile-dependent m=0 threshold scan",
            },
            source_span_text=source_span(text, "four to five times more shear", "m = 0"),
        ),
    ]
    return paper, claims, evidence


def _geyko2019(pdf_path: Path, text: str) -> tuple[Json, list[Json], list[Json]]:
    paper_id = "geyko2019_gyrokinetic"
    paper = _paper(
        paper_id,
        "Gyrokinetic simulations of m=0 mode in sheared flow Z-pinch plasmas",
        pdf_path,
        text,
        year=2019,
        authors=["V. I. Geyko", "M. Dorf", "J. R. Angus"],
    )
    claims = [
        _claim(
            "G_01",
            paper_id,
            "Electrostatic gyrokinetic simulations capture m=0 physics missing from ideal MHD at short scales.",
            home_regime={
                "system": "flowing Z-pinch",
                "framework": "electrostatic gyrokinetic simulation",
                "regime_keywords": ["gyrokinetic", "short-scale", "cogent"],
            },
            weaknesses=[
                "The model is electrostatic and long-wavelength FLR terms are a controlled approximation.",
                "The near-axis unmagnetized region is excluded.",
            ],
            predictions=[_pred("ideal_mhd_short_scale_valid", 0.0)],
            source_span_text=source_span(text, "failing to adequately predict short-scale", "ideal MHD"),
        ),
        _claim(
            "G_02",
            paper_id,
            "Increasing axial flow shear reduces the linear growth rate of m=0 modes in gyrokinetic simulations.",
            home_regime={
                "system": "flowing Z-pinch",
                "framework": "electrostatic gyrokinetic simulation",
                "regime_keywords": ["gyrokinetic", "m = 0", "shear"],
            },
            weaknesses=[
                "The result concerns m=0 axisymmetric modes rather than the m=1 kink mode.",
            ],
            predictions=[_pred("m0_growth_reduced", 1.0)],
            source_span_text=source_span(text, "reduction of the linear growth rate", "increasing shear"),
        ),
    ]
    evidence = [
        _evidence(
            "ev_geyko_mhd_short_scale_fails",
            paper_id,
            "Ideal MHD agrees at long wavelength but fails to predict short-scale stability.",
            dimensions=[_dim("ideal_mhd_short_scale_valid", 0.0)],
            context={
                "system": "flowing Z-pinch",
                "framework": "electrostatic gyrokinetic simulation",
                "regime": "short-scale k rho_i stability",
            },
            source_span_text=source_span(text, "failing to adequately predict short-scale", "ideal MHD"),
        ),
        _evidence(
            "ev_geyko_m0_growth_reduced",
            paper_id,
            "Gyrokinetic runs show reduced m=0 growth rate as shear increases.",
            dimensions=[_dim("m0_growth_reduced", 1.0)],
            context={
                "system": "flowing Z-pinch",
                "framework": "electrostatic gyrokinetic simulation",
                "regime": "axisymmetric m=0 sheared-flow scans",
            },
            source_span_text=source_span(text, "reduction of the linear growth rate", "increasing shear"),
        ),
    ]
    return paper, claims, evidence


_ATLAS_PAPERS = {
    "atlasf__1d_z_pinches_paper_draft_2026-3": ("atlas2026", "Kumar et al. 2026 (Atlas)", 2026),
    "newcomb1960": ("newcomb1960", "Newcomb 1960", 1960),
    "frieman1960": ("frieman1960", "Frieman-Rotenberg 1960", 1960),
    "bondeson1989": ("bondeson1989", "Bondeson-Iacono 1989", 1989),
    "hameiri1981": ("hameiri1981", "Hameiri 1981", 1981),
    "hameiri1985": ("hameiri1985", "Hameiri 1985", 1985),
    "angus2020": ("angus2020", "Angus et al. 2020", 2020),
    "shumlak1995": ("shumlak1995", "Shumlak-Hartman 1995", 1995),
    "shumlak2001": ("shumlak2001", "Shumlak 2001 (ZaP)", 2001),
    "090701_1_5.0227375": ("zhang2019", "Zhang et al. 2019 (FuZE)", 2019),
    "1806.05894v4": ("crews2024", "Crews et al. 2024", 2024),
    "chandrasekhar1957": ("chandrasekhar1957", "Chandrasekhar-Kendall 1957", 1957),
    "mahajan1998": ("mahajan1998", "Mahajan-Yoshida 1998", 1998),
    "shiraishi2005": ("shiraishi2005", "Shiraishi et al. 2005", 2005),
    "2404.06636v1": ("mahajan2024", "Mahajan-Sharma-Lingam 2024", 2024),
    "2510.25532v2": ("sainterme2026", "Sainterme-Ebrahimi 2026", 2026),
    "goedbloed_2022_apjs_259_65": ("goedbloed2022", "Goedbloed-Keppens 2022", 2022),
    "2404.06925v2": ("brughmans2024", "Brughmans et al. 2024", 2024),
    "physrevlett.129.115001": ("wang2022", "Wang et al. 2022 (SMRI exp)", 2022),
    "2010.14148v2": ("claes2020", "Claes et al. 2020 (Legolas)", 2020),
    "2206.07377v1": ("dejonghe2022", "De Jonghe et al. 2022", 2022),
}

_ATLAS_CLAIMS = [
    ("atlas2026", "A_01", "5 constraints H1-H5 are necessary and sufficient for m=1 stability in rotating helical Z-pinch"),
    ("atlas2026", "A_02", "H3 quartic Alfven minimum is the structural ingredient absent from shear-flow-only treatments"),
    ("atlas2026", "A_03", "Discrete spectrum near quartic continuum minimum accumulates as n^-4 with sharp exponent"),
    ("atlas2026", "A_04", "Bi-orthogonal Picone identity generalizes Newcomb node-counting to non-self-adjoint operators"),
    ("atlas2026", "A_05", "Below SARI bound M_A<1, ideal-MHD m=1 growth rate is zero in the asymptotic d_i/R -> 0 regime"),
    ("atlas2026", "A_06", "Framework closes prior conjectures around helical flow, Hameiri Sturmian structure, n^-4 sharpness, SARI exclusion, and kink obstruction"),
    ("atlas2026", "A_07", "RIGID-BELTRAMI-A double-Beltrami equilibrium achieves beta=12.3% with all H1-H5 satisfied"),
    ("newcomb1960", "N_01", "Static Z-pinch at finite pressure cannot be linearly stable to m=1 in ideal MHD"),
    ("newcomb1960", "N_02", "Number of unstable eigenvalues equals number of interior nodes of the marginal mode"),
    ("frieman1960", "FR_01", "Linear MHD stability with stationary flow is governed by a non-Hermitian operator"),
    ("hameiri1981", "H_01", "Sufficient stability conditions for rotating screw-pinch follow from circle theorems and spectral bounds"),
    ("hameiri1985", "H_02", "Essential spectrum of ideal MHD with flow consists of Doppler-shifted Alfven and slow continua"),
    ("bondeson1989", "B_01", "In toroidal or cylindrical geometry, rotation mitigates but does not eliminate kink at finite pressure"),
    ("shumlak1995", "S_01", "Sheared axial flow v'/(kV_A) above about 0.1 stabilizes the m=0 sausage mode in static Z-pinch"),
    ("shumlak2001", "S_02", "ZaP experiment observes a long stable period coincident with sheared sub-Alfvenic flow"),
    ("angus2020", "AN_01", "Linear shear flow alone does not stabilize m=1 kink across realistic Z-pinch profile classes"),
    ("angus2020", "AN_02", "Required shear for m=0 stabilization scales with profile-dependent shear-free growth; m=1 needs a different mechanism"),
    ("chandrasekhar1957", "CK_01", "Force-free curl H = alpha H fields admit poloidal and toroidal eigenfunction solutions"),
    ("mahajan1998", "MY_01", "Coupled magnetofluid admits two-parameter double-Beltrami equilibria with non-trivial flow and pressure"),
    ("shiraishi2005", "SH_01", "Hall effect regularizes the Alfven singularity over a layer of thickness about d_i"),
    ("mahajan2024", "ML_01", "Hall MHD waves are fundamentally distinct from MHD waves at d_i scales"),
    ("sainterme2026", "SE_01", "In the Hall regime, global whistler instabilities grow significantly faster than ideal-MHD modes"),
    ("goedbloed2022", "GK_01", "Super-Alfvenic Rotational Instability emerges from overlap of Doppler-shifted Alfven continua"),
    ("goedbloed2022", "GK_02", "At M_A >= 1 continuum overlap opens uncontrolled SARI spectrum"),
    ("brughmans2024", "BR_01", "Non-axisymmetric SARI modes are confirmed numerically by Legolas with growth rates comparable to MRI"),
    ("wang2022", "W_01", "Axisymmetric SMRI is directly observed in a liquid-metal Taylor-Couette experiment"),
    ("claes2020", "CL_01", "Legolas finite-element MHD spectroscopy computes the full eigenspectrum for 1D equilibria with flow"),
    ("dejonghe2022", "DJ_01", "Legolas extension with viscosity and Hall current is benchmarked against historic results"),
    ("crews2024", "CR_01", "Kadomtsev interchange criterion has an entropy-gradient interpretation analogous to Schwarzschild-Ledoux"),
    ("zhang2019", "Z_01", "FuZE experimentally demonstrates sustained microsecond-scale neutron production during a quiescent period"),
]

_ATLAS_CLAIM_NOTES = {
    "A_01": (
        ["States the central H1-H5 stability claim and is connected to several Atlas evidence pieces."],
        ["Sufficiency depends on every H condition being correctly stated, checked, and physically realizable."],
    ),
    "A_02": (
        ["Identifies H3 as the structural ingredient that separates Atlas from shear-flow-only arguments."],
        ["Needs source audit that comparator papers truly lack the H3 quartic mechanism rather than using different language."],
    ),
    "A_03": (
        ["Makes a sharp spectral accumulation claim that can be tested numerically and analytically."],
        ["The n^-4 exponent may be sensitive to asymptotic assumptions, discretization, and how the continuum minimum is resolved."],
    ),
    "A_04": (
        ["Links Newcomb-style counting to the non-self-adjoint setting needed for flow."],
        ["The scalar seed may hide technical assumptions required for the bi-orthogonal Picone identity."],
    ),
    "A_05": (
        ["Gives a concrete stability boundary below M_A=1 and ties directly to zero-growth Atlas evidence."],
        ["Limited to ideal MHD and the d_i/R -> 0 regime; Hall, kinetic, nonlinear, and finite-device effects remain outside."],
    ),
    "A_06": (
        ["Synthesizes several older conjecture threads into one proposed closure story."],
        ["Broad closure claims are fragile until every referenced conjecture is checked against its original scope."],
    ),
    "A_07": (
        ["Provides a concrete RIGID-BELTRAMI-A equilibrium with beta and H1-H5 checks."],
        ["Constructive equilibrium evidence still needs experimental realizability and robustness checks."],
    ),
    "N_01": (
        ["Gives the classic static finite-beta m=1 obstruction that Atlas must explain around."],
        ["It is a static-regime claim; applying it at full strength to rotating helical H3 configurations overreaches."],
    ),
    "N_02": (
        ["Provides a precise node-counting diagnostic rather than only a qualitative instability statement."],
        ["The diagnostic is not automatically valid for the non-self-adjoint flow operator without additional machinery."],
    ),
    "FR_01": (
        ["Establishes that stationary flow creates non-Hermitian MHD stability structure."],
        ["Overstability possibility is broad and does not by itself determine the Atlas H3 stability boundary."],
    ),
    "H_01": (
        ["Connects rotating screw-pinch stability to spectral bounds and circle-theorem style constraints."],
        ["Sufficient conditions may be conservative and may not map exactly to the Atlas H1-H5 formulation."],
    ),
    "H_02": (
        ["Identifies Doppler-shifted continua as central to ideal MHD with flow."],
        ["Continuum structure alone does not decide whether the sub-Alfvenic Atlas regime is stable."],
    ),
    "B_01": (
        ["Strong historical comparator showing rotation can mitigate kink without eliminating it."],
        ["The studied geometries do not include the full Atlas H3 helical structure, so full-strength projection is too broad."],
    ),
    "S_01": (
        ["Gives a concrete m=0 shear threshold that is useful for mode-family separation."],
        ["It addresses m=0 sausage stabilization, not the m=1 kink closure claimed by Atlas."],
    ),
    "S_02": (
        ["Anchors the graph in ZaP experimental quiescence rather than only theory."],
        ["Observed quiescence and shear coincidence do not by themselves prove the Atlas H3 mechanism."],
    ),
    "AN_01": (
        ["Strong modern comparator showing shear-only linear ideal MHD does not stabilize m=1 in tested profiles."],
        ["The tested profiles may omit the Atlas H3 quartic/helical ingredient, so the negative result should be scoped."],
    ),
    "AN_02": (
        ["Separates m=0 shear scaling from the unresolved m=1 mechanism."],
        ["The scaling is model/profile dependent and should not be treated as a universal threshold."],
    ),
    "CK_01": (
        ["Supplies force-free eigenfunction foundations for Beltrami-style construction."],
        ["Force-free basis results are foundational, not direct stability evidence for Atlas."],
    ),
    "MY_01": (
        ["Supports the existence of double-Beltrami equilibria with flow and pressure."],
        ["Equilibrium existence does not automatically imply spectral stability."],
    ),
    "SH_01": (
        ["Shows Hall terms regularize the ideal-MHD singular layer at finite d_i."],
        ["That regularization may alter, not merely preserve, the Atlas ideal-MHD spectrum."],
    ),
    "ML_01": (
        ["Flags that Hall-scale waves can differ qualitatively from ideal-MHD waves."],
        ["It is a regime warning rather than direct evidence against the Atlas asymptotic theorem."],
    ),
    "SE_01": (
        ["Adds a concrete Hall-regime instability channel to test against Atlas-stable profiles."],
        ["Whistler instability evidence may apply only outside the precise Atlas parameter regime."],
    ),
    "GK_01": (
        ["Explains the SARI mechanism through continuum overlap."],
        ["It describes the super-Alfvenic instability mechanism, not the sub-Alfvenic exclusion side by itself."],
    ),
    "GK_02": (
        ["Defines M_A >= 1 as a natural operating boundary for Atlas."],
        ["The transition near M_A=1 still needs width and robustness analysis."],
    ),
    "BR_01": (
        ["Numerically confirms non-axisymmetric SARI behavior with a spectral code."],
        ["It is primarily evidence for the unstable side of the boundary, not for Atlas stability below it."],
    ),
    "W_01": (
        ["Provides experimental support that rotation-driven MHD instabilities can be observed in the lab."],
        ["SMRI is axisymmetric and not the same non-axisymmetric SARI/kink regime as Atlas."],
    ),
    "CL_01": (
        ["Provides numerical infrastructure for full-spectrum MHD checks."],
        ["Benchmark capability is indirect unless the Atlas equilibrium is actually run through the code."],
    ),
    "DJ_01": (
        ["Extends numerical tooling toward viscosity and Hall current effects."],
        ["Tool validation is not a substitute for a targeted Atlas-profile computation."],
    ),
    "CR_01": (
        ["Connects interchange criteria to an entropy-gradient interpretation that may clarify mode families."],
        ["The analogy may not transfer cleanly to helical flow with H3 without further derivation."],
    ),
    "Z_01": (
        ["Adds FuZE operational evidence for quiescent, neutron-producing Z-pinch plasmas."],
        ["Neutron production and quiescence do not identify the exact m=1 stabilization mechanism."],
    ),
}

_ATLAS_EVIDENCE = [
    ("atlas2026", "ev_atlas_kink_zero", "|gamma_m=1| < 8e-12 tau_A^-1 on RIGID-BELTRAMI-A at beta=12.3%", 1.0),
    ("atlas2026", "ev_atlas_pseudospec", "epsilon-pseudospectrum boundary stays below 4.1e-7 tau_A^-1 in the upper half-plane", 1.0),
    ("atlas2026", "ev_atlas_newcomb_bench", "ARPACK recovers Newcomb 1960 m=1 eigenvalues to 1e-5 relative accuracy", 1.0),
    ("atlas2026", "ev_atlas_h3_value", "|F''(r*)|/F_max = 0.41/R^2 confirms the H3 quartic minimum", 1.0),
    ("atlas2026", "ev_atlas_120pts", "All 120 sampled (m,k) points satisfy |gamma|<1e-11 tau_A^-1", 1.0),
    ("atlas2026", "ev_atlas_h1_violate", "Violating H1 with q_min=0.92 produces an unstable kink", 0.0),
    ("atlas2026", "ev_atlas_h3_violate", "Violating H3 gives n^-2 Suydam accumulation and finite growth", 0.0),
    ("newcomb1960", "ev_newcomb_static", "Static finite-beta Z-pinch has unstable m=1 spectrum", 0.0),
    ("shumlak1995", "ev_shumlak_threshold", "m=0 stabilization at v'/(kV_A) around 0.1 is demonstrated numerically", 1.0),
    ("shumlak2001", "ev_shumlak_zap", "ZaP stable period of 15-20 microseconds is coincident with shear", 1.0),
    ("angus2020", "ev_angus_m1_persists", "m=1 kink remains unstable at all tested shear levels on realistic profiles", 0.0),
    ("angus2020", "ev_angus_m0_scaling", "m=0 shear-stabilization scaling follows profile-dependent growth-rate scaling", 0.85),
    ("bondeson1989", "ev_bondeson_toroidal", "Toroidal rotation mitigates but does not eliminate kink in the cylindrical analogue", 0.0),
    ("goedbloed2022", "ev_goedbloed_sari", "SARI modes fill two-dimensional continua in the eigenfrequency plane at M_A>1", 0.0),
    ("brughmans2024", "ev_brughmans_growth", "Non-axisymmetric SARI growth rates are comparable to MRI at high mode numbers", 0.0),
    ("shiraishi2005", "ev_shiraishi_dilayer", "Hall-MHD solutions converge to ideal MHD outside a d_i-scale neighborhood of the singularity", 1.0),
    ("sainterme2026", "ev_sainterme_whistler", "Global whistler instabilities grow faster than ideal-MHD modes at d_i/L of a few percent", 0.0),
    ("wang2022", "ev_wang_smri", "Axisymmetric SMRI onset is observed at critical magnetic Reynolds number", 0.0),
    ("zhang2019", "ev_zhang_neutrons", "FuZE sustains neutron emission during the quiescent period with density-squared scaling", 1.0),
    ("crews2024", "ev_crews_entropy", "Kadomtsev marginal-stable profile has an entropy-gradient interpretation", 1.0),
    ("hameiri1985", "ev_hameiri_continuum", "Ideal MHD with flow has Doppler-shifted Alfven continua governing essential spectrum", 1.0),
    ("frieman1960", "ev_friman_overstable", "Stationary-flow MHD operator is non-Hermitian, so overstability is possible", 1.0),
    ("chandrasekhar1957", "ev_chandra_ck", "Force-free curl H=alpha H is solvable in a poloidal and toroidal basis", 1.0),
    ("mahajan1998", "ev_mahajan_db", "Double-curl Beltrami equilibrium admits non-trivial pressure and minimum-|B| confinement", 1.0),
    ("claes2020", "ev_legolas_bench", "Legolas reproduces canonical MHD spectra across benchmark problems", 1.0),
]

_ATLAS_EDGES = [
    ("A_01", "ev_atlas_kink_zero", 1.0, "in_regime"),
    ("A_01", "ev_atlas_120pts", 1.0, "in_regime"),
    ("A_01", "ev_atlas_h1_violate", 0.0, "in_regime"),
    ("A_01", "ev_atlas_h3_violate", 0.0, "in_regime"),
    ("A_02", "ev_atlas_h3_value", 1.0, "in_regime"),
    ("A_02", "ev_atlas_h3_violate", 0.0, "in_regime"),
    ("A_03", "ev_atlas_h3_value", 1.0, "in_regime"),
    ("A_04", "ev_atlas_kink_zero", 1.0, "in_regime"),
    ("A_04", "ev_atlas_newcomb_bench", 1.0, "in_regime"),
    ("A_05", "ev_atlas_kink_zero", 1.0, "in_regime"),
    ("A_05", "ev_atlas_pseudospec", 1.0, "in_regime"),
    ("A_05", "ev_atlas_120pts", 1.0, "in_regime"),
    ("A_06", "ev_atlas_kink_zero", 1.0, "in_regime"),
    ("A_07", "ev_atlas_h3_value", 1.0, "in_regime"),
    ("A_07", "ev_atlas_kink_zero", 1.0, "in_regime"),
    ("A_05", "ev_newcomb_static", 0.0, "out_of_regime"),
    ("A_05", "ev_angus_m1_persists", 0.0, "out_of_regime"),
    ("A_05", "ev_bondeson_toroidal", 0.0, "out_of_regime"),
    ("A_02", "ev_angus_m1_persists", 0.0, "out_of_regime"),
    ("A_05", "ev_goedbloed_sari", 0.0, "out_of_regime"),
    ("A_05", "ev_brughmans_growth", 0.0, "out_of_regime"),
    ("A_07", "ev_chandra_ck", 1.0, "in_regime"),
    ("A_07", "ev_mahajan_db", 1.0, "in_regime"),
    ("A_04", "ev_friman_overstable", 1.0, "in_regime"),
    ("A_04", "ev_hameiri_continuum", 1.0, "in_regime"),
    ("N_01", "ev_newcomb_static", 0.0, "in_regime"),
    ("N_02", "ev_newcomb_static", 0.0, "in_regime"),
    ("N_02", "ev_atlas_newcomb_bench", 1.0, "in_regime"),
    ("N_01", "ev_atlas_kink_zero", 0.0, "out_of_regime"),
    ("N_01", "ev_atlas_h3_violate", 0.0, "in_regime"),
    ("FR_01", "ev_friman_overstable", 1.0, "in_regime"),
    ("FR_01", "ev_atlas_pseudospec", 1.0, "in_regime"),
    ("H_01", "ev_hameiri_continuum", 1.0, "in_regime"),
    ("H_02", "ev_hameiri_continuum", 1.0, "in_regime"),
    ("H_02", "ev_goedbloed_sari", 0.0, "out_of_regime"),
    ("B_01", "ev_bondeson_toroidal", 0.0, "in_regime"),
    ("B_01", "ev_atlas_kink_zero", 0.0, "out_of_regime"),
    ("S_01", "ev_shumlak_threshold", 1.0, "in_regime"),
    ("S_02", "ev_shumlak_zap", 1.0, "in_regime"),
    ("S_01", "ev_angus_m0_scaling", 0.85, "out_of_regime"),
    ("AN_01", "ev_angus_m1_persists", 0.0, "in_regime"),
    ("AN_02", "ev_angus_m0_scaling", 0.85, "in_regime"),
    ("AN_01", "ev_atlas_kink_zero", 0.0, "out_of_regime"),
    ("CK_01", "ev_chandra_ck", 1.0, "in_regime"),
    ("MY_01", "ev_mahajan_db", 1.0, "in_regime"),
    ("MY_01", "ev_atlas_h3_value", 1.0, "out_of_regime"),
    ("SH_01", "ev_shiraishi_dilayer", 1.0, "in_regime"),
    ("SH_01", "ev_atlas_kink_zero", 1.0, "out_of_regime"),
    ("ML_01", "ev_sainterme_whistler", 0.0, "out_of_regime"),
    ("SE_01", "ev_sainterme_whistler", 0.0, "in_regime"),
    ("SE_01", "ev_atlas_kink_zero", 1.0, "out_of_regime"),
    ("GK_01", "ev_goedbloed_sari", 0.0, "in_regime"),
    ("GK_02", "ev_goedbloed_sari", 0.0, "in_regime"),
    ("GK_02", "ev_atlas_kink_zero", 1.0, "out_of_regime"),
    ("BR_01", "ev_brughmans_growth", 0.0, "in_regime"),
    ("BR_01", "ev_goedbloed_sari", 0.0, "out_of_regime"),
    ("W_01", "ev_wang_smri", 0.0, "in_regime"),
    ("CL_01", "ev_legolas_bench", 1.0, "in_regime"),
    ("DJ_01", "ev_legolas_bench", 1.0, "in_regime"),
    ("CL_01", "ev_brughmans_growth", 0.0, "out_of_regime"),
    ("Z_01", "ev_zhang_neutrons", 1.0, "in_regime"),
    ("CR_01", "ev_crews_entropy", 1.0, "in_regime"),
    ("CR_01", "ev_shumlak_threshold", 1.0, "out_of_regime"),
]

_ATLAS_IDEAS = [
    (
        "idea_01_m1_stability_via_H3",
        "m=1 stability of rotating helical Z-pinch is closed by the H3 quartic Alfven minimum",
        ["A_01", "A_02", "A_03", "A_04", "A_05", "A_06", "A_07", "N_01", "AN_01", "B_01"],
        [
            "ev_atlas_kink_zero",
            "ev_atlas_h3_value",
            "ev_atlas_120pts",
            "ev_atlas_h1_violate",
            "ev_atlas_h3_violate",
            "ev_atlas_pseudospec",
            "ev_newcomb_static",
            "ev_angus_m1_persists",
            "ev_bondeson_toroidal",
        ],
        "Atlas separates the rotating helical H3 regime from older static or shear-only kink obstructions.",
    ),
    (
        "idea_02_static_obstruction_genealogy",
        "The static finite-beta m=1 obstruction survives as a special-case limit",
        ["N_01", "N_02", "FR_01", "B_01", "AN_01", "CR_01"],
        [
            "ev_newcomb_static",
            "ev_bondeson_toroidal",
            "ev_angus_m1_persists",
            "ev_atlas_newcomb_bench",
            "ev_atlas_h3_violate",
            "ev_crews_entropy",
        ],
        "The older obstruction is real, but the atlas data scopes it to a narrower regime.",
    ),
    (
        "idea_03_hall_regularization",
        "Hall corrections at finite d_i/R regularize the H3 singularity over a d_i layer",
        ["SH_01", "ML_01", "SE_01", "A_05", "A_02"],
        ["ev_shiraishi_dilayer", "ev_sainterme_whistler", "ev_atlas_kink_zero"],
        "The ideal-MHD atlas regime becomes a reference point for finite-ion-skin-depth corrections.",
    ),
    (
        "idea_04_sari_boundary",
        "Atlas's regime ends at M_A=1 where SARI continuum overlap takes over",
        ["GK_01", "GK_02", "BR_01", "W_01", "A_05", "H_02"],
        ["ev_goedbloed_sari", "ev_brughmans_growth", "ev_wang_smri", "ev_atlas_kink_zero", "ev_hameiri_continuum"],
        "The SARI literature marks the super-Alfvenic boundary of the atlas-stable region.",
    ),
    (
        "idea_05_shumlak_m0_complementary",
        "Shumlak's m=0 sheared-flow stabilization is complementary rather than competing",
        ["S_01", "S_02", "AN_02", "CR_01", "Z_01", "A_06"],
        ["ev_shumlak_threshold", "ev_shumlak_zap", "ev_angus_m0_scaling", "ev_zhang_neutrons", "ev_crews_entropy"],
        "The Shumlak mode family and atlas m=1 theorem can be read as two halves of a joint stability story.",
    ),
    (
        "idea_06_mathematical_and_numerical_foundations",
        "Beltrami, operator, and numerical foundations support the Atlas construction",
        ["CK_01", "MY_01", "H_01", "FR_01", "CL_01", "DJ_01"],
        ["ev_chandra_ck", "ev_mahajan_db", "ev_hameiri_continuum", "ev_friman_overstable", "ev_legolas_bench"],
        "Foundational Beltrami equilibria, non-Hermitian flow operators, and spectral solvers provide the substrate on which the Atlas argument is built.",
    ),
]


def _atlas_seed(pdf_path: Path, text: str) -> tuple[Json, list[Json], list[Json]] | None:
    spec = _ATLAS_PAPERS.get(pdf_path.stem.lower())
    if not spec:
        return None

    paper_id, title, year = spec
    paper = _paper(paper_id, title, pdf_path, text, year=year, authors=[])
    claims = [
        _claim(
            claim_id,
            paper_id,
            label,
            home_regime=_atlas_home_regime(paper_id),
            strengths=_atlas_claim_strengths(claim_id),
            weaknesses=_atlas_claim_weaknesses(claim_id),
            predictions=[
                _pred(evidence_id, value, evidence_ids=[evidence_id], regime_tag=regime_tag)
                for source, evidence_id, value, regime_tag in _ATLAS_EDGES
                if source == claim_id
            ],
            source_span_text=source_span(text),
            confidence=0.72 if paper_id == "atlas2026" else 0.66,
        )
        for claim_paper, claim_id, label in _ATLAS_CLAIMS
        if claim_paper == paper_id
    ]
    evidence = [
        _evidence(
            evidence_id,
            paper_id,
            label,
            dimensions=[_dim(evidence_id, value)],
            context=_atlas_context(paper_id),
            source_span_text=source_span(text),
            confidence=0.74 if paper_id == "atlas2026" else 0.68,
        )
        for evidence_paper, evidence_id, label, value in _ATLAS_EVIDENCE
        if evidence_paper == paper_id
    ]
    return paper, claims, evidence


def _atlas_claim_strengths(claim_id: str) -> list[str]:
    notes = _ATLAS_CLAIM_NOTES.get(claim_id)
    if notes:
        return list(notes[0])
    return ["Connects a seeded literature claim to explicit graph predictions."]


def _atlas_claim_weaknesses(claim_id: str) -> list[str]:
    notes = _ATLAS_CLAIM_NOTES.get(claim_id)
    if notes:
        return list(notes[1])
    return ["Needs source-span and regime-scope review before being treated as authoritative."]


def _atlas_home_regime(paper_id: str) -> Json:
    groups = {
        "atlas2026": ("rotating helical Z-pinch", "ideal MHD Atlas H1-H5", ["atlas", "h3", "rigid-beltrami"]),
        "newcomb1960": ("static Z-pinch", "ideal MHD node counting", ["newcomb", "static"]),
        "angus2020": ("sheared-flow Z-pinch", "linear ideal MHD eigenmode analysis", ["angus", "shear", "profile"]),
        "shumlak1995": ("sheared-flow Z-pinch", "linear and numerical MHD", ["shumlak", "m=0", "shear"]),
        "shumlak2001": ("ZaP Z-pinch experiment", "experiment", ["zap", "quiescent", "shear"]),
        "goedbloed2022": ("rotating plasma", "SARI spectral theory", ["sari", "alfven", "ma"]),
        "brughmans2024": ("rotating plasma", "Legolas SARI computation", ["sari", "legolas"]),
        "shiraishi2005": ("Hall-MHD singular layer", "Hall MHD", ["hall", "di"]),
        "sainterme2026": ("Hall-MHD plasma", "whistler instability", ["hall", "whistler"]),
    }
    system, framework, keywords = groups.get(paper_id, ("magnetized plasma", "MHD literature", [paper_id]))
    return {"system": system, "framework": framework, "regime_keywords": keywords}


def _atlas_context(paper_id: str) -> Json:
    home = _atlas_home_regime(paper_id)
    return {
        "system": home["system"],
        "framework": home["framework"],
        "regime": ", ".join(home["regime_keywords"]),
    }


def atlas_seeded_ideas(corpus_name: str, claims: list[Json], evidence: list[Json], sheaf: Json) -> list[Json] | None:
    if corpus_name != "atlas":
        return None
    claim_ids = {claim["claim_id"] for claim in claims}
    evidence_ids = {ev["evidence_id"] for ev in evidence}
    if "A_01" not in claim_ids or "ev_atlas_kink_zero" not in evidence_ids:
        return None

    ideas: list[Json] = []
    for idea_id, title, raw_claims, raw_evidence, summary in _ATLAS_IDEAS:
        idea_claims = [claim_id for claim_id in raw_claims if claim_id in claim_ids]
        idea_evidence = [ev_id for ev_id in raw_evidence if ev_id in evidence_ids]
        edge_ids = {
            edge["edge_id"]
            for edge in sheaf["edges"]
            if edge["claim_id"] in idea_claims and edge["evidence_id"] in idea_evidence
        }
        resolved = [
            {
                "edge_id": edge["edge_id"],
                "resolution": f"{edge['claim_id']} narrowed its out-of-regime strength.",
            }
            for edge in sheaf["edges"]
            if edge["edge_id"] in edge_ids
            and any(op["claim_id"] == edge["claim_id"] for op in sheaf["operations"])
        ]
        remaining = [
            tension for tension in sheaf["remaining_tensions"] if tension["edge_id"] in edge_ids
        ]
        ideas.append(
            {
                "idea_id": idea_id,
                "title": title,
                "description": summary,
                "scope": {
                    "system": "Atlas Z-pinch corpus",
                    "framework": "seeded v0.5 restriction-rewriting graph",
                    "regime": summary,
                },
                "contributing_claims": idea_claims,
                "contributing_evidence": idea_evidence,
                "tensions_resolved": resolved,
                "remaining_tensions": remaining,
                "open_questions": _atlas_open_questions(idea_id, bool(remaining)),
                "transitions_out": [],
                "provenance": {
                    "consolidator": "deterministic_atlas_seed",
                    "corpus": corpus_name,
                },
            }
        )
    return ideas


def _atlas_open_questions(idea_id: str, has_remaining: bool) -> list[Json]:
    questions = {
        "idea_01_m1_stability_via_H3": "Which finite-device and nonlinear effects are still outside the H3 ideal-MHD closure?",
        "idea_02_static_obstruction_genealogy": "Where exactly does the static Newcomb obstruction stop applying once helical rotation and H3 are present?",
        "idea_03_hall_regularization": "Does the n^-4 accumulation survive at finite d_i/R, or is it replaced by a Hall-modified spectrum?",
        "idea_04_sari_boundary": "How wide is the transition region as M_A approaches 1 from below?",
        "idea_05_shumlak_m0_complementary": "Can a ZaP or FuZE-class device realize a profile satisfying both Shumlak m=0 shear and Atlas m=1 H3 conditions?",
        "idea_06_mathematical_and_numerical_foundations": "Which foundation pieces need direct validation before they can support the Atlas construction?",
    }
    priorities = {
        "idea_01_m1_stability_via_H3": "high",
        "idea_02_static_obstruction_genealogy": "medium",
        "idea_03_hall_regularization": "high",
        "idea_04_sari_boundary": "medium",
        "idea_05_shumlak_m0_complementary": "exploratory",
        "idea_06_mathematical_and_numerical_foundations": "medium",
    }
    next_steps = {
        "idea_01_m1_stability_via_H3": [
            _next_work(
                "simulation",
                "Finite-length Atlas profile scan",
                "Run resistive and nonlinear MHD on RIGID-BELTRAMI-A-like profiles with finite-length boundaries, then compare m=1 growth against the ideal d_i/R -> 0 prediction.",
            ),
            _next_work(
                "theory",
                "Nonlinear remainder bound",
                "Identify which nonlinear terms are excluded by the H1-H5 theorem and derive a perturbative bound for how large they can be before the closure fails.",
            ),
            _next_work(
                "experiment",
                "Profile-realizability diagnostic",
                "Design magnetic and flow diagnostics that can confirm whether an experimental pinch actually realizes the H3 quartic minimum and sub-Alfvenic rotation profile.",
            ),
        ],
        "idea_02_static_obstruction_genealogy": [
            _next_work(
                "theory",
                "Assumption homotopy",
                "Write the exact sequence of assumptions that transforms Newcomb's static operator into the Atlas non-self-adjoint helical-flow operator.",
            ),
            _next_work(
                "simulation",
                "Static-to-H3 profile continuation",
                "Numerically continue profiles from a Newcomb-unstable static pinch to an Atlas H3 profile and track where the m=1 eigenvalue changes sign.",
            ),
            _next_work(
                "literature",
                "Comparator source audit",
                "Check Newcomb, Bondeson-Iacono, and Angus source assumptions line-by-line against Atlas H1-H5 so each rewrite is scoped precisely.",
            ),
        ],
        "idea_03_hall_regularization": [
            _next_work(
                "simulation",
                "Hall-MHD d_i/R sweep",
                "Run a Hall-MHD eigenvalue scan on the Atlas equilibrium for d_i/R from near zero to compact-pinch values and track the spectral accumulation exponent.",
            ),
            _next_work(
                "theory",
                "Matched asymptotic H3 layer",
                "Derive the inner Hall layer correction near the H3 quartic minimum and match it to the outer ideal-MHD solution.",
            ),
            _next_work(
                "experiment",
                "Hall-scale sensitivity check",
                "Estimate whether available devices operate at d_i/R large enough for Hall regularization to be a leading-order effect.",
            ),
        ],
        "idea_04_sari_boundary": [
            _next_work(
                "simulation",
                "Approach M_A = 1 from below",
                "Sweep M_A upward on the Atlas equilibrium and measure how the least-stable non-axisymmetric modes behave before continuum overlap.",
            ),
            _next_work(
                "theory",
                "Transition-width asymptotics",
                "Derive the scaling law for residual growth as M_A approaches one and identify whether H3 delays or sharpens the SARI onset.",
            ),
            _next_work(
                "experiment",
                "Rotation-boundary measurement",
                "Map achievable radial rotation and Alfven speed profiles to determine whether devices can stay safely below the SARI boundary.",
            ),
        ],
        "idea_05_shumlak_m0_complementary": [
            _next_work(
                "experiment",
                "Joint m=0/m=1 profile target",
                "Design a ZaP/FuZE-class discharge target that satisfies Shumlak's m=0 shear threshold and approximates Atlas H3 conditions.",
            ),
            _next_work(
                "simulation",
                "Common-profile stability check",
                "Run a shared equilibrium through both m=0 shear-stabilization analysis and m=1 Atlas-style spectral analysis.",
            ),
            _next_work(
                "theory",
                "Mode-family coupling",
                "Derive whether satisfying the m=0 and m=1 conditions simultaneously creates new higher-m or mixed-mode constraints.",
            ),
        ],
        "idea_06_mathematical_and_numerical_foundations": [
            _next_work(
                "theory",
                "Foundation-to-H1-H5 map",
                "Map the Chandrasekhar-Kendall, Mahajan-Yoshida, Hameiri, and Frieman operator assumptions onto the exact Atlas H1-H5 requirements.",
            ),
            _next_work(
                "simulation",
                "Independent spectral benchmark",
                "Run the Atlas equilibrium through a Legolas-style or shooting-method benchmark and compare eigenvalues against the seeded pseudospectral result.",
            ),
            _next_work(
                "audit",
                "Foundational source audit",
                "Verify each foundation source is being used at its native scope instead of being promoted into direct experimental evidence.",
            ),
        ],
    }
    items = [
        {
            "question": questions[idea_id],
            "priority": priorities[idea_id],
            "suggested_next_steps": next_steps[idea_id],
        }
    ]
    if has_remaining:
        items.append(
            {
                "question": "Which remaining residuals are real contradictions rather than seeded-scope artifacts?",
                "priority": "blocking",
                "suggested_next_steps": [
                    _next_work(
                        "audit",
                        "Residual edge review",
                        "Inspect each remaining high-residual edge against the source PDFs and decide whether the edge, regime tag, or claim scope is wrong.",
                    ),
                    _next_work(
                        "theory",
                        "Scope split proposal",
                        "If a residual is real, split the broad claim into separate home-regime and cross-regime claims instead of weakening the evidence.",
                    ),
                ],
            }
        )
    return items


def _next_work(kind: str, title: str, description: str) -> Json:
    return {"kind": kind, "title": title, "description": description}


def _fallback(pdf_path: Path, text: str) -> tuple[Json, list[Json], list[Json]]:
    paper_id = pdf_path.stem.lower().replace(" ", "_")
    title = pdf_path.stem
    paper = _paper(paper_id, title, pdf_path, text, year=None, authors=[])
    claim = _claim(
        f"{paper_id}_C01",
        paper_id,
        f"{title} contains extractable scientific claims requiring review.",
        home_regime={"system": "", "framework": "", "regime_keywords": []},
        weaknesses=["No deterministic extractor seed is available for this paper."],
        predictions=[],
        source_span_text=source_span(text),
        confidence=0.25,
    )
    return paper, [claim], []
