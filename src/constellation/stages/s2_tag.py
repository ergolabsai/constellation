"""Stage 2: tag claims with (semilattice, SNAG) coordinates.

See ARCHITECTURE.md Stage 2: Tag claims with (semilattice, SNAG) coordinates

Two sub-steps:

  2a. propose vocabulary — the LLM looks at the whole corpus (papers + claims)
      and proposes a tag vocabulary: semilattice dimensions (each with values
      and ordering) plus a SNAG node vocabulary. Output: tag_vocabulary.json.

  2b. tag claims — the LLM tags each claim against that vocabulary. Output:
      augmented claims with ._tags field containing semilattice + SNAG coordinates.

If tag_vocabulary.json already exists in the run directory, sub-step 2a is
SKIPPED — this is the "review and iterate" path: the user edits the vocabulary
by hand, then re-runs `--from 2 --to 2` to retag claims under the new vocab.

Claims are loaded as Claim domain objects; tags augment each claim's ._tags
field and are persisted when serializing claims via .to_dict().
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from rich.console import Console

from ..config import model_name, stage_config, get_mvp_config
from ..failures import append_stage_failures, clear_stage_failures
from ..llm import LLM, parse_json_response
from ..llm_cache import lookup as cache_lookup
from ..llm_cache import write_success as cache_write_success
from ..objects import Claim
from ..paths import Corpus, Run
from ..prompt_loader import load_prompt

console = Console()
STAGE_NAME = "stage2_tag"

# ---------- shared loaders ---------------------------------------------------


def _load_corpus(run: Run) -> tuple[list[dict], list[Claim]]:
    """Read all paper.json and claim.json artifacts produced by stage 1.

    Papers are returned as dicts (used only for vocabulary proposal summary).
    Claims are returned as domain objects (will be augmented with ._tags).
    """
    papers = [json.loads(p.read_text()) for p in sorted(run.papers_dir.glob("*.json"))]
    claims = [Claim.from_dict(json.loads(p.read_text())) for p in sorted(run.claims_dir.glob("*.json"))]
    return papers, claims


def _claim_summary(claim: Claim | dict) -> dict:
    """Compact projection of a claim — enough to tag against, not the whole record.

    Accepts both Claim objects (from stage 2) and dicts (from stage 1 during
    vocabulary proposal).
    """
    if isinstance(claim, Claim):
        claim_dict = claim.to_dict()
    else:
        claim_dict = claim
    return {
        "claim_id": claim_dict["claim_id"],
        "paper_id": claim_dict["paper_id"],
        "claim_type": claim_dict.get("claim_type"),
        "cause": claim_dict.get("cause"),
        "effect": claim_dict.get("effect"),
        "direction": claim_dict.get("direction"),
        "scope_evidenced": claim_dict.get("scope", {}).get("evidenced"),
    }


def _paper_summary(paper: dict) -> dict:
    """Compact paper projection — observational ground only, not the full DAG."""
    return {
        "paper_id": paper["paper_id"],
        "title": paper.get("bibliographic", {}).get("title"),
        "model_level": paper.get("model_level"),
        "paper_type": paper.get("paper_type"),
        "observational_ground": paper.get("observational_ground"),
    }


# ---------- 2a: vocabulary proposal ------------------------------------------


def _propose_vocabulary(
    llm: LLM, run: Run, papers: list[dict], claims: list[dict]
) -> dict:
    """One LLM call. Returns the parsed tag_vocabulary dict."""
    system = load_prompt("s2a_propose_vocabulary")

    corpus_payload = {
        "papers": [_paper_summary(p) for p in papers],
        "claims": [_claim_summary(c) for c in claims],
    }
    user_text = (
        "Propose a tag vocabulary for the following corpus. Return ONLY the "
        "JSON object as specified.\n\n# Corpus\n\n```json\n"
        + json.dumps(corpus_payload, indent=2)
        + "\n```"
    )

    messages = [{"role": "user", "content": [{"type": "text", "text": user_text}]}]
    cache_handle = cache_lookup(
        run=run,
        stage="stage2_propose_vocabulary",
        llm=llm,
        system=system,
        messages=messages,
        max_tokens=8192,
    )
    if cache_handle.hit:
        text = cache_handle.raw_response
        vocab = cache_handle.parsed_response
    else:
        text = llm.chat(system=system, messages=messages, max_tokens=8192)
        vocab = parse_json_response(text)
    _validate_vocabulary(vocab)
    cache_write_success(cache_handle, raw_response=text, parsed_response=vocab)
    return vocab


def _validate_vocabulary(vocab: Any) -> None:
    """Light structural check — schema is informal at MVP."""
    if not isinstance(vocab, dict):
        raise ValueError("vocabulary must be a JSON object")
    for required in ("semilattice_dimensions", "snag_nodes"):
        if required not in vocab:
            raise ValueError(f"vocabulary missing required key: {required}")
    if not isinstance(vocab["semilattice_dimensions"], list) or not vocab["semilattice_dimensions"]:
        raise ValueError("semilattice_dimensions must be a non-empty list")
    if not isinstance(vocab["snag_nodes"], list) or not vocab["snag_nodes"]:
        raise ValueError("snag_nodes must be a non-empty list")

    seen_dims = set()
    for dim in vocab["semilattice_dimensions"]:
        # For hierarchical dimensions, the hierarchy keys ARE the values; derive
        # `values` from them if the LLM omitted it. (Strict requirement
        # otherwise — a discrete dim without `values` is genuinely malformed.)
        if (
            "values" not in dim
            and dim.get("ordering") == "hierarchical"
            and isinstance(dim.get("hierarchy"), dict)
        ):
            dim["values"] = sorted(dim["hierarchy"].keys())

        for required in ("name", "values", "ordering"):
            if required not in dim:
                raise ValueError(f"dimension missing required key '{required}': {dim}")
        if dim["name"] in seen_dims:
            raise ValueError(f"duplicate dimension name: {dim['name']}")
        seen_dims.add(dim["name"])
        if dim["ordering"] not in ("discrete", "hierarchical", "set_inclusion"):
            raise ValueError(
                f"dimension {dim['name']!r} has unknown ordering {dim['ordering']!r}"
            )
        if dim["ordering"] == "hierarchical" and "hierarchy" not in dim:
            raise ValueError(
                f"hierarchical dimension {dim['name']!r} missing 'hierarchy' field"
            )

    seen_snag = set()
    for node in vocab["snag_nodes"]:
        if "canonical" not in node:
            raise ValueError(f"SNAG node missing 'canonical' key: {node}")
        if node["canonical"] in seen_snag:
            raise ValueError(f"duplicate SNAG canonical: {node['canonical']}")
        seen_snag.add(node["canonical"])


def _load_or_propose_vocabulary(
    llm: LLM, run: Run, papers: list[dict], claims: list[dict]
) -> tuple[dict, bool]:
    """Returns (vocab, freshly_proposed)."""
    if run.tag_vocabulary_path.exists():
        console.print(
            f"  [dim]reusing existing tag_vocabulary.json "
            f"({run.tag_vocabulary_path.stat().st_size} bytes)[/dim]"
        )
        vocab = json.loads(run.tag_vocabulary_path.read_text())
        _validate_vocabulary(vocab)
        return vocab, False

    console.print("  proposing tag vocabulary…")
    vocab = _propose_vocabulary(llm, run, papers, claims)
    run.tag_vocabulary_path.write_text(json.dumps(vocab, indent=2))
    return vocab, True


# ---------- 2b: per-claim tagging --------------------------------------------


def _tag_one_batch(
    llm: LLM,
    run: Run,
    vocab: dict,
    batch: list[dict],
    system: str,
    *,
    max_retries: int,
) -> dict[str, Any]:
    """Tag one batch of claims. Per-batch retry on JSON/validation failure."""
    payload = [_claim_summary(c) for c in batch]
    user_text = (
        "Tag the following claims using the vocabulary in the system prompt. "
        "Return ONLY the JSON object keyed by claim_id.\n\n# Claims\n\n```json\n"
        + json.dumps(payload, indent=2)
        + "\n```"
    )
    messages = [{"role": "user", "content": [{"type": "text", "text": user_text}]}]
    last_error: Exception | None = None
    for attempt in range(max_retries + 1):
        cache_handle = cache_lookup(
            run=run,
            stage="stage2_tag_claims",
            llm=llm,
            system=system,
            messages=messages,
            max_tokens=16384,
        )
        try:
            if cache_handle.hit:
                text = cache_handle.raw_response
                tags = cache_handle.parsed_response
            else:
                text = llm.chat(system=system, messages=messages, max_tokens=16384)
                tags = parse_json_response(text)
            _validate_tags(tags, vocab, batch)
            cache_write_success(cache_handle, raw_response=text, parsed_response=tags)
            return tags
        except (ValueError, json.JSONDecodeError) as e:
            last_error = e
            if attempt == max_retries:
                break
            console.print(f"    [yellow]tag attempt {attempt + 1} failed[/yellow]: {e}")
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
        f"batch tagging failed after {max_retries + 1} attempts: {last_error}"
    )


def _tag_claims(
    llm: LLM,
    run: Run,
    vocab: dict,
    claims: list[Claim],
    *,
    max_retries: int,
    tag_batch_size: int,
    allow_partial: bool,
) -> None:
    """Tag all claims by chunking into batches.

    Augments each Claim object with ._tags field. A single call for hundreds of
    claims hits two failure modes: (1) max_tokens truncation, (2) the model losing
    structural fidelity over very long outputs. Chunking bounds both. Per-batch
    failures don't kill the run — we log and continue only when allow_partial is
    enabled; strict mode records failures and raises.
    """
    system_template = load_prompt("s2b_tag_claims")
    system = system_template.replace("{vocabulary_json}", json.dumps(vocab, indent=2))

    n_batches = (len(claims) + tag_batch_size - 1) // tag_batch_size
    n_tagged = 0
    failures: list[dict[str, Any]] = []

    for i in range(n_batches):
        batch = claims[i * tag_batch_size : (i + 1) * tag_batch_size]
        batch_dicts = [c.to_dict() for c in batch]
        console.print(
            f"    batch {i + 1}/{n_batches}: tagging {len(batch)} claims…"
        )
        try:
            batch_tags = _tag_one_batch(
                llm,
                run,
                vocab,
                batch_dicts,
                system,
                max_retries=max_retries,
            )
            # Augment Claim objects with ._tags
            for claim in batch:
                if claim.claim_id in batch_tags:
                    claim.tags = batch_tags[claim.claim_id]
                    n_tagged += 1
        except Exception as e:
            failures.append(
                {
                    "kind": "tag_batch_failed",
                    "batch": i + 1,
                    "claim_ids": [c.claim_id for c in batch],
                    "error": str(e),
                }
            )
            console.print(f"      [red]batch {i + 1} failed[/red]: {e}")

    if failures:
        append_stage_failures(run, STAGE_NAME, failures)
        console.print(
            f"  [yellow]warning[/yellow]: {len(failures)}/{n_batches} tag batches "
            f"failed; {n_tagged}/{len(claims)} claims tagged"
        )
        if not allow_partial:
            raise RuntimeError(
                f"stage 2 failed for {len(failures)} tag batch(es); "
                f"see {run.failures_path}"
            )
    if n_tagged == 0:
        raise RuntimeError("tagging produced no successful batches")


def _validate_tags(tags: Any, vocab: dict, claims: list[dict]) -> None:
    """Verify each claim is tagged and every value is in the vocabulary."""
    if not isinstance(tags, dict):
        raise ValueError("tags output must be a JSON object keyed by claim_id")

    expected = {c["claim_id"] for c in claims}
    got = set(tags.keys())
    missing = expected - got
    extra = got - expected
    if missing or extra:
        raise ValueError(
            f"claim_id mismatch: missing tags for {sorted(missing)}, "
            f"unexpected ids in tags {sorted(extra)}"
        )

    dim_values = {
        d["name"]: set(d["values"]) | {None} for d in vocab["semilattice_dimensions"]
    }
    snag_canonicals = {n["canonical"] for n in vocab["snag_nodes"]}

    for cid, tag in tags.items():
        if not isinstance(tag, dict):
            raise ValueError(f"tag for {cid} must be an object")
        sl = tag.get("semilattice", {})
        if not isinstance(sl, dict):
            raise ValueError(f"tag.semilattice for {cid} must be an object")
        for dim, value in sl.items():
            if dim not in dim_values:
                raise ValueError(f"tag for {cid} uses unknown dimension {dim!r}")
            if value not in dim_values[dim]:
                raise ValueError(
                    f"tag for {cid} dimension {dim!r} has value {value!r} "
                    f"not in vocabulary"
                )
        snag = tag.get("snag_nodes", [])
        if not isinstance(snag, list):
            raise ValueError(f"tag.snag_nodes for {cid} must be an array")
        for node in snag:
            if node not in snag_canonicals:
                raise ValueError(
                    f"tag for {cid} uses unknown SNAG node {node!r}"
                )


# ---------- orchestration ----------------------------------------------------


def run(corpus: Corpus, run: Run) -> None:  # noqa: A002 (intentional shadow of builtin)
    clear_stage_failures(run, STAGE_NAME)
    cfg = get_mvp_config(run, corpus)
    llm = LLM(model=model_name(run, corpus))
    papers, claims = _load_corpus(run)
    if not claims:
        raise RuntimeError(
            f"no claims found under {run.claims_dir}; run stage 1 first"
        )

    console.print(f"loaded {len(papers)} papers, {len(claims)} claims from run dir")

    vocab, freshly_proposed = _load_or_propose_vocabulary(llm, run, papers, claims)
    n_dims = len(vocab["semilattice_dimensions"])
    n_snag = len(vocab["snag_nodes"])
    fresh_label = "freshly proposed" if freshly_proposed else "reused from disk"
    console.print(
        f"  [green]vocabulary[/green] ({fresh_label}): "
        f"{n_dims} dimensions, {n_snag} SNAG nodes"
    )

    console.print(f"  tagging {len(claims)} claims…")
    _tag_claims(
        llm,
        run,
        vocab,
        claims,
        max_retries=cfg.max_retries_stage2,
        tag_batch_size=cfg.tag_batch_size,
        allow_partial=cfg.allow_partial_stage2,
    )

    # Write claims back to disk with ._tags field populated
    for claim in claims:
        claim_dict = claim.to_dict()
        claim_path = run.claims_dir / f"{claim.claim_id.replace(':', '_')}.json"
        claim_path.write_text(json.dumps(claim_dict, indent=2))

    # Quick stats for the operator
    n_tagged = sum(1 for c in claims if c.tags)
    total_snag_links = sum(len(c.tags.get("snag_nodes", [])) for c in claims if c.tags)
    avg_snag = total_snag_links / max(n_tagged, 1)
    console.print(
        f"  [green]tagged[/green] {n_tagged}/{len(claims)} claims "
        f"(avg {avg_snag:.1f} SNAG nodes per claim)"
    )

    # If the user wants to inspect the vocab before stage 3, this is the moment.
    if freshly_proposed:
        console.print(
            f"  [dim]review {_relative(run.tag_vocabulary_path)} before running stage 3 — "
            f"edit and re-run `--from 2 --to 2` to retag with a revised vocabulary[/dim]"
        )


def _relative(p: Path) -> str:
    try:
        return str(p.relative_to(Path.cwd()))
    except ValueError:
        return str(p)
