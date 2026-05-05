"""Tests for structured failures.json helpers."""
from __future__ import annotations

from pathlib import Path

from constellation.failures import (
    append_stage_failures,
    clear_stage_failures,
    load_failures,
)
from constellation.paths import Run


def _run(tmp_path: Path) -> Run:
    root = tmp_path / "runs" / "toy"
    root.mkdir(parents=True)
    return Run(root)


def test_append_stage_failures_writes_manifest(tmp_path: Path):
    run = _run(tmp_path)

    append_stage_failures(
        run,
        "stage2_tag",
        [{"kind": "tag_batch_failed", "batch": 1, "error": "bad"}],
    )

    doc = load_failures(run)
    assert run.failures_path.exists()
    assert doc["failures"]["stage2_tag"][0]["kind"] == "tag_batch_failed"
    assert doc["failures"]["stage2_tag"][0]["batch"] == 1


def test_clear_stage_failures_removes_stale_entries(tmp_path: Path):
    run = _run(tmp_path)
    append_stage_failures(run, "stage1_extract", [{"kind": "x"}])
    append_stage_failures(run, "stage2_tag", [{"kind": "y"}])

    clear_stage_failures(run, "stage1_extract")
    doc = load_failures(run)

    assert "stage1_extract" not in doc["failures"]
    assert "stage2_tag" in doc["failures"]


def test_clear_last_stage_failure_removes_manifest(tmp_path: Path):
    run = _run(tmp_path)
    append_stage_failures(run, "stage1_extract", [{"kind": "x"}])

    clear_stage_failures(run, "stage1_extract")

    assert not run.failures_path.exists()
