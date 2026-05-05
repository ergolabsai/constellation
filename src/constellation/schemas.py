"""Schema validation against the four JSON schemas in the project root.

The .json files in the project root are the source of truth for artifact shape;
this module loads them once and exposes validators. Pipeline stages produce
plain dicts and validate before writing.

We deliberately do NOT mirror the schemas as Pydantic models. Hand-maintained
parallel models drift from the JSON sources; jsonschema validation against the
source-of-truth files prevents that.
"""
from __future__ import annotations

import json
from functools import cache
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

# Repo root: src/constellation/schemas.py -> ../../..
SCHEMA_DIR = Path(__file__).resolve().parents[2]

PAPER = "paper_schema.json"
CLAIM = "claim_schema.json"
SHEAF = "sheaf_schema.json"
IDEA = "idea_schema.json"
EPSILON_MACHINE = "epsilon_machine_schema.json"


@cache
def _load(name: str) -> dict[str, Any]:
    return json.loads((SCHEMA_DIR / name).read_text())


@cache
def _validator(name: str) -> Draft202012Validator:
    schema = _load(name)
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


def validate_paper(d: dict[str, Any]) -> None:
    _validator(PAPER).validate(d)


def validate_claim(d: dict[str, Any]) -> None:
    _validator(CLAIM).validate(d)


def validate_sheaf(d: dict[str, Any]) -> None:
    _validator(SHEAF).validate(d)


def validate_idea(d: dict[str, Any]) -> None:
    _validator(IDEA).validate(d)


def validate_epsilon_machine(d: dict[str, Any]) -> None:
    _validator(EPSILON_MACHINE).validate(d)
