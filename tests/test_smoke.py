"""Smoke tests for the skeleton: imports, schemas load, CLI is wired."""
from __future__ import annotations

from typer.testing import CliRunner


def test_package_import():
    import constellation

    assert constellation.__version__ == "0.1.0"


def test_schemas_load_and_are_valid_json_schema():
    from constellation.schemas import _load, _validator

    for name in (
        "paper_schema.json",
        "claim_schema.json",
        "sheaf_schema.json",
        "idea_schema.json",
    ):
        d = _load(name)
        assert d["$schema"].startswith("https://json-schema.org/")
        assert d["title"]
        # _validator() runs Draft202012Validator.check_schema(); raises if invalid.
        _validator(name)


def test_cli_help_runs():
    from constellation.cli import app

    r = CliRunner().invoke(app, ["--help"])
    assert r.exit_code == 0
    assert "constellation" in r.stdout.lower() or "run" in r.stdout.lower()


def test_pipeline_lists_nine_stages():
    from constellation.pipeline import STAGES

    assert [s.n for s in STAGES] == list(range(1, 10))
    assert {s.name for s in STAGES} == {
        "extract", "tag", "complex", "alternatives", "compatibility",
        "map", "frustration", "consolidate", "report",
    }


def test_all_stages_callable():
    """All 9 stages should be importable and have a `run` function."""
    from constellation.pipeline import STAGES

    for stage in STAGES:
        assert callable(stage.fn), f"stage {stage.n}: {stage.name} is not callable"
