"""Tests for stage 1's pure helpers (no LLM calls)."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from constellation.llm import parse_json_response
from constellation.paper_loader import paper_to_user_blocks
from constellation.prompt_loader import load_prompt
from constellation.stages.s1_extract import (
    _build_system_prompt,
    _check_dag_consistency,
    _claim_filename,
    _stamp_provenance,
)

# ---------- paper_loader -----------------------------------------------------


def test_paper_to_user_blocks_returns_document_block(tmp_path: Path):
    pdf = tmp_path / "tiny.pdf"
    pdf.write_bytes(b"%PDF-1.4\n%fake\n")
    blocks = paper_to_user_blocks(pdf)
    assert len(blocks) == 1
    assert blocks[0]["type"] == "document"
    assert blocks[0]["source"]["media_type"] == "application/pdf"
    assert blocks[0]["source"]["type"] == "base64"
    assert isinstance(blocks[0]["source"]["data"], str)


def test_paper_to_user_blocks_rejects_non_pdf(tmp_path: Path):
    f = tmp_path / "notes.txt"
    f.write_text("hi")
    with pytest.raises(ValueError, match="expected .pdf"):
        paper_to_user_blocks(f)


# ---------- prompt_loader ----------------------------------------------------


def test_load_prompt_finds_s1_template():
    text = load_prompt("s1_extract")
    assert "Paper schema" in text
    assert "{paper_schema_json}" in text
    assert "{claim_schema_json}" in text


def test_load_prompt_missing_raises():
    with pytest.raises(FileNotFoundError):
        load_prompt("does_not_exist")


# ---------- system prompt assembly -------------------------------------------


def test_build_system_prompt_embeds_both_schemas():
    prompt = _build_system_prompt()
    # Paper schema
    assert '"$id": "landscape-map/paper/v0.5"' in prompt
    # Claim schema
    assert '"$id": "landscape-map/claim/v0.5"' in prompt
    # Template placeholders should be gone
    assert "{paper_schema_json}" not in prompt
    assert "{claim_schema_json}" not in prompt


# ---------- parse_json_response ----------------------------------------------


def test_parse_json_response_plain():
    assert parse_json_response('{"a": 1}') == {"a": 1}


def test_parse_json_response_strips_json_fence():
    text = '```json\n{"a": 1}\n```'
    assert parse_json_response(text) == {"a": 1}


def test_parse_json_response_strips_bare_fence():
    text = '```\n{"a": 1}\n```'
    assert parse_json_response(text) == {"a": 1}


def test_parse_json_response_extracts_from_prose():
    text = 'Here is the result:\n{"a": 1}\nLet me know if you need more.'
    assert parse_json_response(text) == {"a": 1}


def test_parse_json_response_raises_on_garbage():
    with pytest.raises(json.JSONDecodeError):
        parse_json_response("just plain text, no json at all")


# ---------- _claim_filename --------------------------------------------------


def test_claim_filename_replaces_colon():
    assert _claim_filename("shumlak2009:01") == "shumlak2009_01.json"
    assert _claim_filename("paper:CN-03") == "paper_CN-03.json"


# ---------- _stamp_provenance ------------------------------------------------


def test_stamp_provenance_sets_method_and_model():
    paper: dict = {}
    claims: list[dict] = [{}, {"extraction": {"method": "manual"}}]
    _stamp_provenance(paper, claims, model="claude-sonnet-4-6")

    assert paper["extraction"]["method"] == "llm_single"
    assert paper["extraction"]["model"] == "claude-sonnet-4-6"
    # First claim: empty -> stamped
    assert claims[0]["extraction"]["method"] == "llm_single"
    assert claims[0]["extraction"]["model"] == "claude-sonnet-4-6"
    # Second claim: existing method preserved, model overridden
    assert claims[1]["extraction"]["method"] == "manual"
    assert claims[1]["extraction"]["model"] == "claude-sonnet-4-6"


# ---------- _check_dag_consistency -------------------------------------------


def _mk(paper_dag: list[dict], claim_ids: list[str]) -> tuple[dict, list[dict]]:
    paper = {"claims": paper_dag}
    claims = [{"claim_id": cid} for cid in claim_ids]
    return paper, claims


def test_check_dag_ok():
    paper, claims = _mk(
        [
            {"claim_id": "p:01", "depends_on": []},
            {"claim_id": "p:02", "depends_on": ["p:01"]},
        ],
        ["p:01", "p:02"],
    )
    _check_dag_consistency(paper, claims)


def test_check_dag_detects_cycle():
    paper, claims = _mk(
        [
            {"claim_id": "p:01", "depends_on": ["p:02"]},
            {"claim_id": "p:02", "depends_on": ["p:01"]},
        ],
        ["p:01", "p:02"],
    )
    with pytest.raises(ValueError, match="cycle"):
        _check_dag_consistency(paper, claims)


def test_check_dag_detects_unknown_dep():
    paper, claims = _mk(
        [
            {"claim_id": "p:01", "depends_on": ["p:99"]},
        ],
        ["p:01"],
    )
    with pytest.raises(ValueError, match="unknown claim_id"):
        _check_dag_consistency(paper, claims)


def test_check_dag_detects_id_mismatch():
    paper, claims = _mk(
        [{"claim_id": "p:01", "depends_on": []}],
        ["p:01", "p:02"],  # extra claim missing from DAG
    )
    with pytest.raises(ValueError, match="disagree"):
        _check_dag_consistency(paper, claims)
