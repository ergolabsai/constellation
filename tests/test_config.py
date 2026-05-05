"""Tests for run_config.json creation and lookup."""
from __future__ import annotations

import json
from pathlib import Path

from constellation.config import (
    DEFAULT_STAGE_CONFIG,
    ensure_run_config,
    stage_config,
)
from constellation.paths import Corpus, Run


def _run(tmp_path: Path) -> tuple[Corpus, Run]:
    corpus_root = tmp_path / "corpora" / "toy"
    corpus_root.mkdir(parents=True)
    run_root = tmp_path / "runs" / "toy_20260505T000000Z"
    run_root.mkdir(parents=True)
    return Corpus(corpus_root), Run(run_root)


def test_ensure_run_config_writes_default_snapshot(tmp_path: Path):
    corpus, run = _run(tmp_path)
    config = ensure_run_config(run, corpus)

    assert run.run_config_path.exists()
    on_disk = json.loads(run.run_config_path.read_text())
    assert on_disk == config
    assert config["corpus"] == "toy"
    assert config["pipeline_version"] == "v2_paper_as_stalk"
    assert config["model"]
    assert config["stages"]["stage1_extract"]["allow_partial"] is False
    assert config["stages"]["stage6_map"]["lambda_rewrite_penalty"] == 0.4
    assert config["stages"]["stage6_map"]["lambda_sensitivity_values"] == [
        0.1,
        0.2,
        0.4,
        0.8,
    ]
    assert config["schemas"]["claim"] == "landscape-map/claim/v0.5"
    assert (
        config["schemas"]["epsilon_machine"]
        == "landscape-map/epsilon_machine/v0.1"
    )
    assert config["prompts"]["score_compatibility"].startswith("sha256:")


def test_ensure_run_config_preserves_existing_file(tmp_path: Path):
    corpus, run = _run(tmp_path)
    existing = {
        "model": "custom-model",
        "stages": {"stage3_complex": {"snag_overlap_threshold": 4}},
    }
    run.run_config_path.write_text(json.dumps(existing))

    assert ensure_run_config(run, corpus) == existing


def test_stage_config_merges_defaults_with_overrides(tmp_path: Path):
    corpus, run = _run(tmp_path)
    run.run_config_path.write_text(
        json.dumps(
            {
                "stages": {
                    "stage6_map": {
                        "lambda_rewrite_penalty": 0.8,
                    }
                }
            }
        )
    )

    cfg = stage_config(run, corpus, "stage6_map")
    assert cfg["lambda_rewrite_penalty"] == 0.8
    assert cfg["enumerate_limit"] == DEFAULT_STAGE_CONFIG["stage6_map"]["enumerate_limit"]
