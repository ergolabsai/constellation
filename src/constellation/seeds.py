from __future__ import annotations

from pathlib import Path

from .util import Json, source_span


def extract_seeded_records(pdf_path: Path, text: str) -> tuple[Json, list[Json], list[Json]]:
    name = pdf_path.name.lower()
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


def _pred(observable: str, value: float, *, scale: str = "normalized_binary") -> Json:
    return {"observable": observable, "value": value, "scale": scale}


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

