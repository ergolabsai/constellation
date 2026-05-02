"""Pairwise compatibility scoring — shared by stages 4 and 5.

Stage 4 uses this for original-original pairs (and decides which trigger
alternative generation). Stage 5 uses it for every variant pair to fill out
the full compatibility cube. Same rubric, same prompt, same output shape.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from .llm import LLM, parse_json_response
from .prompt_loader import load_prompt

VALID_KINDS = (
    "agreement",
    "extension",
    "refinement",
    "qualification",
    "boundary",
    "contradiction",
)


@dataclass(frozen=True)
class VariantHandle:
    """A variant of a claim, ready to be scored.

    For the `#original`, `text` is the canonical paraphrase
    `{cause} {direction} {effect}`. For rewrites, `text` is the variant's
    own restated claim from the stalk.
    """

    claim_id: str
    variant_id: str   # e.g. "shumlak2009:02#original" or "...#alt_correlate"
    text: str
    full_claim: dict   # the full claim record (for evidence lookup)


def canonical_text(claim: dict) -> str:
    """Default `text` for an `#original` variant."""
    parts = [
        str(claim.get("cause", "")),
        str(claim.get("direction", "")),
        str(claim.get("effect", "")),
    ]
    text = " ".join(p for p in parts if p)
    conds = (
        claim.get("scope", {}).get("evidenced", {}).get("conditions") or []
    )
    if conds:
        text += f"  (evidenced under: {'; '.join(conds)})"
    return text


def _build_user_payload(
    a: VariantHandle,
    b: VariantHandle,
    semilattice_meet: dict,
    snag_overlap: list[str],
) -> str:
    """Compose the per-call user message for a scoring request."""
    payload = {
        "claim_a": {
            "claim_id": a.claim_id,
            "variant_id": a.variant_id,
            "text": a.text,
            "scope_claimed": a.full_claim.get("scope", {}).get("claimed"),
            "scope_evidenced": a.full_claim.get("scope", {}).get("evidenced"),
            "evidence": a.full_claim.get("evidence"),
            "direction": a.full_claim.get("direction"),
        },
        "claim_b": {
            "claim_id": b.claim_id,
            "variant_id": b.variant_id,
            "text": b.text,
            "scope_claimed": b.full_claim.get("scope", {}).get("claimed"),
            "scope_evidenced": b.full_claim.get("scope", {}).get("evidenced"),
            "evidence": b.full_claim.get("evidence"),
            "direction": b.full_claim.get("direction"),
        },
        "semilattice_meet": semilattice_meet,
        "snag_overlap": snag_overlap,
    }
    return (
        "Score the following pair according to the rubric. Return ONLY the "
        "JSON object.\n\n```json\n"
        + json.dumps(payload, indent=2)
        + "\n```"
    )


def _validate_score(result: Any) -> dict:
    if not isinstance(result, dict):
        raise ValueError("scoring response must be a JSON object")
    for k in ("score", "kind", "explanation"):
        if k not in result:
            raise ValueError(f"scoring response missing required key: {k}")
    score = result["score"]
    if not isinstance(score, int | float) or not (-1.0 <= score <= 1.0):
        raise ValueError(f"score must be a number in [-1, 1], got {score!r}")
    if result["kind"] not in VALID_KINDS:
        raise ValueError(
            f"kind must be one of {VALID_KINDS}, got {result['kind']!r}"
        )
    # Score-kind consistency check (loose — within the schema's documented bands)
    if result["kind"] == "contradiction" and score >= -0.2:
        raise ValueError(
            f"kind='contradiction' requires score < -0.2, got {score}"
        )
    if result["kind"] == "agreement" and score < 0.6:
        raise ValueError(
            f"kind='agreement' requires score >= 0.6, got {score}"
        )
    if not isinstance(result["explanation"], str) or not result["explanation"].strip():
        raise ValueError("explanation must be a non-empty string")
    return {
        "score": float(score),
        "kind": result["kind"],
        "explanation": result["explanation"].strip(),
    }


def score_pair(
    *,
    a: VariantHandle,
    b: VariantHandle,
    semilattice_meet: dict,
    snag_overlap: list[str],
    llm: LLM,
    max_retries: int = 1,
) -> dict:
    """Score one variant pair. Returns a dict matching sheaf_schema's
    `compatibility_scores[]` shape: {variant_a_id, variant_b_id, score, kind, explanation}.

    Retries once on validation failure with an error-feedback follow-up.
    """
    system = load_prompt("score_compatibility")
    user_text = _build_user_payload(a, b, semilattice_meet, snag_overlap)
    messages = [{"role": "user", "content": [{"type": "text", "text": user_text}]}]

    last_error: Exception | None = None
    for attempt in range(max_retries + 1):
        try:
            text = llm.chat(system=system, messages=messages, max_tokens=1024)
            parsed = parse_json_response(text)
            valid = _validate_score(parsed)
            return {
                "variant_a_id": a.variant_id,
                "variant_b_id": b.variant_id,
                **valid,
            }
        except (ValueError, json.JSONDecodeError) as e:
            last_error = e
            if attempt == max_retries:
                break
            messages = [
                *messages,
                {"role": "assistant", "content": [{"type": "text", "text": text}]},
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": (
                                f"Your previous output failed validation:\n\n{e}\n\n"
                                "Re-emit the corrected JSON object."
                            ),
                        }
                    ],
                },
            ]
    raise RuntimeError(
        f"scoring {a.variant_id} ↔ {b.variant_id} failed: {last_error}"
    )
