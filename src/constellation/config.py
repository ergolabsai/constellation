"""Run configuration snapshot.

The pipeline's defaults live here so new runs can persist the exact knobs they
used. Stages read from `run_config.json` instead of importing scattered module
constants, which makes completed runs easier to compare and reproduce.

See ARCHITECTURE.md Configuration Parameters section for MVP defaults.
"""
from __future__ import annotations

import json
import os
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import UTC, datetime
from hashlib import sha256
from typing import Any

from dotenv import load_dotenv

from .paths import Corpus, Run
from .prompt_loader import PROMPTS_DIR
from .schemas import CLAIM, EPSILON_MACHINE, IDEA, PAPER, SHEAF, _load

load_dotenv(override=True)

PIPELINE_VERSION = "v2_paper_as_stalk"
DEFAULT_MODEL = os.environ.get("CONSTELLATION_MODEL", "claude-sonnet-4-6")


@dataclass
class MVPConfig:
    """MVP configuration defaults per ARCHITECTURE.md Configuration Parameters section.

    These are the canonical MVP defaults used across all pipeline stages. Each
    parameter is documented with its purpose and stage. Stages should read from
    this unified source rather than hardcoding values.
    """

    # ========== Extraction (Stage 1) ==========
    llm_model: str = DEFAULT_MODEL

    # ========== Tagging (Stage 2) ==========
    semilattice_tag_dimensions: int = 6
    tag_batch_size: int = 30

    # ========== Comparability (Stage 3) ==========
    # Two claims form a comparability edge iff their semilattice coordinates meet
    # (regime compatibility) AND SNAG nodes overlap by at least this threshold.
    snag_overlap_threshold_literals: int = 2
    snag_overlap_threshold_soft_keywords: int = 1

    # ========== Alternatives (Stage 4) ==========
    # Claims with restriction failure (score < this) trigger alternative generation.
    contest_threshold: float = 0.0
    # Maximum alternatives per claim to prevent stalk explosion.
    max_alternatives_per_claim: int = 3

    # ========== MAP (Stage 6) ==========
    # Primary λ: how aggressively to preserve originals vs. rewrite for coherence.
    # 0.4 is balanced; 0.2 rewrites eagerly, 0.8 preserves strongly.
    lambda_rewrite_penalty: float = 0.4
    # Sweep values to replay MAP without re-scoring; identifies λ-sensitive selections.
    lambda_sensitivity_values: list[float] = field(default_factory=lambda: [0.1, 0.2, 0.4, 0.8])
    # Number of alternative sections to retain for sensitivity analysis.
    n_alternative_sections: int = 4
    # Exhaustive enumeration limit: switch to coord_ascent above this.
    enumerate_limit: int = 100_000
    # Solver: "enumerate" (MVP), "coord_ascent", "ilp", "simulated_annealing" (deferred).
    map_solver: str = "enumerate"
    # Coord ascent: number of random restarts for stochastic optimization.
    coord_ascent_n_restarts: int = 5

    # ========== Consolidation (Stage 8) ==========
    # Minimum claims per Idea (ε-state). Below this, the Idea is suspect.
    min_claims_per_idea: int = 2
    # Frustration (ρ) above this triggers a warning in diagnostics.
    frustration_warning_rho: float = 0.2

    # ========== Validation & Reporting ==========
    # Allow partial failures at stage boundaries if per-item errors occur.
    allow_partial_stage1: bool = False
    allow_partial_stage2: bool = False
    allow_partial_stage4: bool = False
    # Max LLM call retries before failing a stage.
    max_retries_stage1: int = 2
    max_retries_stage2: int = 1
    max_retries_stage4: int = 1
    max_retries_stage8: int = 1

    def to_dict(self) -> dict[str, Any]:
        """Export to dict for run_config.json serialization."""
        return {
            "llm_model": self.llm_model,
            "semilattice_tag_dimensions": self.semilattice_tag_dimensions,
            "tag_batch_size": self.tag_batch_size,
            "snag_overlap_threshold_literals": self.snag_overlap_threshold_literals,
            "snag_overlap_threshold_soft_keywords": self.snag_overlap_threshold_soft_keywords,
            "contest_threshold": self.contest_threshold,
            "max_alternatives_per_claim": self.max_alternatives_per_claim,
            "lambda_rewrite_penalty": self.lambda_rewrite_penalty,
            "lambda_sensitivity_values": self.lambda_sensitivity_values,
            "n_alternative_sections": self.n_alternative_sections,
            "enumerate_limit": self.enumerate_limit,
            "map_solver": self.map_solver,
            "coord_ascent_n_restarts": self.coord_ascent_n_restarts,
            "min_claims_per_idea": self.min_claims_per_idea,
            "frustration_warning_rho": self.frustration_warning_rho,
            "allow_partial_stage1": self.allow_partial_stage1,
            "allow_partial_stage2": self.allow_partial_stage2,
            "allow_partial_stage4": self.allow_partial_stage4,
            "max_retries_stage1": self.max_retries_stage1,
            "max_retries_stage2": self.max_retries_stage2,
            "max_retries_stage4": self.max_retries_stage4,
            "max_retries_stage8": self.max_retries_stage8,
        }

    @staticmethod
    def from_dict(d: dict[str, Any]) -> MVPConfig:
        """Load from run_config.json (or other dict source)."""
        kwargs = {}
        for field_name in MVPConfig.__dataclass_fields__:
            if field_name in d:
                kwargs[field_name] = d[field_name]
        return MVPConfig(**kwargs)


DEFAULT_STAGE_CONFIG: dict[str, dict[str, Any]] = {
    "stage1_extract": {
        "allow_partial": False,
        "max_retries": 2,
    },
    "stage2_tag": {
        "allow_partial": False,
        "max_retries": 1,
        "tag_batch_size": 30,
    },
    "stage3_complex": {
        "snag_overlap_threshold": 2,
    },
    "stage4_alternatives": {
        "allow_partial": False,
        "contest_threshold": 0.0,
        "max_alternatives_per_claim": 3,
        "max_retries": 1,
    },
    "stage6_map": {
        "lambda_rewrite_penalty": 0.4,
        "lambda_sensitivity_values": [0.1, 0.2, 0.4, 0.8],
        "n_alternative_sections": 4,
        "enumerate_limit": 100_000,
        "map_solver": "enumerate",
        "coord_ascent_restarts": 5,
    },
    "stage8_consolidate": {
        "min_claims_per_idea": 2,
        "frustration_warning_rho": 0.2,
        "max_retries": 1,
    },
}


def _schema_ids() -> dict[str, str]:
    """Return the source schema identifiers captured by a run config."""
    return {
        "paper": _load(PAPER).get("$id", PAPER),
        "claim": _load(CLAIM).get("$id", CLAIM),
        "sheaf": _load(SHEAF).get("$id", SHEAF),
        "idea": _load(IDEA).get("$id", IDEA),
        "epsilon_machine": _load(EPSILON_MACHINE).get("$id", EPSILON_MACHINE),
    }


def _prompt_hashes() -> dict[str, str]:
    """Return sha256 hashes for prompt templates captured by a run config."""
    hashes = {}
    for path in sorted(PROMPTS_DIR.glob("*.md")):
        hashes[path.stem] = "sha256:" + sha256(path.read_bytes()).hexdigest()
    return hashes


def default_run_config(corpus: Corpus | None = None) -> dict[str, Any]:
    """Build a fresh run config with current defaults and environment model."""
    return {
        "$schema": "constellation/run_config/v0.1",
        "created_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "pipeline_version": PIPELINE_VERSION,
        "corpus": corpus.name if corpus else None,
        "model": DEFAULT_MODEL,
        "stages": deepcopy(DEFAULT_STAGE_CONFIG),
        "schemas": _schema_ids(),
        "prompts": _prompt_hashes(),
    }


def write_run_config(run: Run, config: dict[str, Any]) -> None:
    """Persist `config` to the run directory."""
    run.run_config_path.write_text(json.dumps(config, indent=2) + "\n")


def ensure_run_config(run: Run, corpus: Corpus | None = None) -> dict[str, Any]:
    """Return the run config, creating it with defaults if missing."""
    if run.run_config_path.exists():
        return json.loads(run.run_config_path.read_text())
    config = default_run_config(corpus)
    write_run_config(run, config)
    return config


def stage_config(run: Run, corpus: Corpus, stage_name: str) -> dict[str, Any]:
    """Return config for one stage, creating run_config.json if necessary."""
    config = ensure_run_config(run, corpus)
    stage_defaults = DEFAULT_STAGE_CONFIG.get(stage_name, {})
    stage_values = config.get("stages", {}).get(stage_name, {})
    return {**stage_defaults, **stage_values}


def model_name(run: Run, corpus: Corpus) -> str:
    """Return the model pinned in this run's config."""
    config = ensure_run_config(run, corpus)
    return str(config.get("model") or DEFAULT_MODEL)


def get_mvp_config(run: Run, corpus: Corpus) -> MVPConfig:
    """Load MVPConfig from run_config.json, falling back to defaults.

    See ARCHITECTURE.md Configuration Parameters section for parameter meanings.
    """
    config = ensure_run_config(run, corpus)
    # Try to load from the top-level mvp_config key (new format)
    if "mvp_config" in config:
        return MVPConfig.from_dict(config["mvp_config"])
    # Fall back to default
    return MVPConfig(llm_model=model_name(run, corpus))
