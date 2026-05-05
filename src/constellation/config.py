"""Run configuration snapshot.

The pipeline's defaults live here so new runs can persist the exact knobs they
used. Stages read from `run_config.json` instead of importing scattered module
constants, which makes completed runs easier to compare and reproduce.
"""
from __future__ import annotations

import json
import os
from copy import deepcopy
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
        "max_retries": 1,
    },
    "stage6_map": {
        "lambda_rewrite_penalty": 0.4,
        "lambda_sensitivity_values": [0.1, 0.2, 0.4, 0.8],
        "n_alternative_sections": 4,
        "enumerate_limit": 100_000,
        "coord_ascent_restarts": 5,
    },
    "stage8_consolidate": {
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
