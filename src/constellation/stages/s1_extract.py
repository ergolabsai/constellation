"""Stage 1: extract paper + claims + argument DAG from each PDF.

Input:  corpus.pdfs()
Output: run.papers_dir/<paper_id>.json    (paper_schema)
        run.claims_dir/<paper_id>_NN.json (claim_schema, N per paper)

One LLM call per paper, with up to MAX_RETRIES additional rounds if the
model's output fails JSON parsing, schema validation, or DAG-acyclicity.
The retry feeds the previous bad output + the error back to the model.

Per-paper failures don't kill the run — we log and continue. A summary is
printed at the end.
"""
from __future__ import annotations

import json
from typing import Any

from jsonschema.exceptions import ValidationError
from rich.console import Console

from ..llm import LLM, parse_json_response
from ..paper_loader import paper_to_user_blocks
from ..paths import Corpus, Run
from ..prompt_loader import load_prompt
from ..schemas import CLAIM, PAPER, _load, validate_claim, validate_paper

console = Console()

MAX_RETRIES = 2  # so up to 3 attempts per paper


def _build_system_prompt() -> str:
    """Embed both schemas into the s1 prompt template.

    Uses str.replace rather than str.format so the example {paper_id} / {year}
    tokens elsewhere in the prompt aren't interpreted as format placeholders.
    """
    template = load_prompt("s1_extract")
    paper_schema = json.dumps(_load(PAPER), indent=2)
    claim_schema = json.dumps(_load(CLAIM), indent=2)
    return (
        template
        .replace("{paper_schema_json}", paper_schema)
        .replace("{claim_schema_json}", claim_schema)
    )


def _claim_filename(claim_id: str) -> str:
    """{paper_id}:NN -> {paper_id}_NN.json (colon is sketchy in some FSes)."""
    return claim_id.replace(":", "_") + ".json"


def _stamp_provenance(paper: dict[str, Any], claims: list[dict[str, Any]], model: str) -> None:
    paper.setdefault("extraction", {})
    paper["extraction"]["method"] = "llm_single"
    paper["extraction"]["model"] = model

    for c in claims:
        c.setdefault("extraction", {})
        c["extraction"].setdefault("method", "llm_single")
        c["extraction"]["model"] = model


def _check_dag_consistency(paper: dict[str, Any], claims: list[dict[str, Any]]) -> None:
    """Verify the argument DAG references only known claim_ids and is acyclic."""
    claim_ids = {c["claim_id"] for c in claims}
    dag_ids = {entry["claim_id"] for entry in paper.get("claims", [])}

    if claim_ids != dag_ids:
        missing_in_dag = claim_ids - dag_ids
        missing_in_claims = dag_ids - claim_ids
        raise ValueError(
            f"paper.claims and claims[] disagree: "
            f"in claims but not DAG={sorted(missing_in_dag)}, "
            f"in DAG but not claims={sorted(missing_in_claims)}"
        )

    deps = {e["claim_id"]: list(e.get("depends_on", [])) for e in paper["claims"]}
    color: dict[str, int] = {cid: 0 for cid in deps}  # 0=white, 1=gray, 2=black

    def visit(cid: str, stack: list[str]) -> None:
        if color[cid] == 2:
            return
        if color[cid] == 1:
            raise ValueError(f"argument DAG has a cycle: {' -> '.join([*stack, cid])}")
        color[cid] = 1
        for dep in deps.get(cid, []):
            if dep not in deps:
                raise ValueError(f"depends_on references unknown claim_id: {cid} -> {dep}")
            visit(dep, [*stack, cid])
        color[cid] = 2

    for cid in deps:
        visit(cid, [])


def _validate_extraction(result: Any) -> tuple[dict, list[dict]]:
    """Run all checks on a candidate extraction. Raises with a fixable message."""
    if not isinstance(result, dict) or "paper" not in result or "claims" not in result:
        raise ValueError(
            "Top-level JSON must be an object with exactly two keys: 'paper' and 'claims'."
        )
    paper = result["paper"]
    claims = result["claims"]
    if not isinstance(claims, list):
        raise ValueError("'claims' must be an array.")

    try:
        validate_paper(paper)
    except ValidationError as e:
        raise ValueError(
            f"paper failed schema validation: {e.message} (at {list(e.absolute_path)})"
        ) from e

    for i, c in enumerate(claims):
        try:
            validate_claim(c)
        except ValidationError as e:
            raise ValueError(
                f"claims[{i}] (id={c.get('claim_id', '?')}) failed schema validation: "
                f"{e.message} (at {list(e.absolute_path)})"
            ) from e

    _check_dag_consistency(paper, claims)
    return paper, claims


def _extract_one_paper(
    llm: LLM, system: str, pdf_path
) -> tuple[dict, list[dict]]:
    """Extract one paper with retry-on-failure. Raises after MAX_RETRIES."""
    user_content = paper_to_user_blocks(pdf_path) + [
        {
            "type": "text",
            "text": (
                "Extract this paper according to the instructions above. "
                "Return ONLY the JSON object."
            ),
        }
    ]
    messages: list[dict[str, Any]] = [{"role": "user", "content": user_content}]

    last_error: Exception | None = None
    for attempt in range(MAX_RETRIES + 1):
        try:
            text = llm.chat(system=system, messages=messages, max_tokens=32768)
            result = parse_json_response(text)
            paper, claims = _validate_extraction(result)
            return paper, claims
        except (ValueError, json.JSONDecodeError) as e:
            last_error = e
            if attempt == MAX_RETRIES:
                break
            console.print(f"    [yellow]attempt {attempt + 1} failed[/yellow]: {e}")
            # Append assistant turn + a corrective user turn for the retry.
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
                                "Re-emit the corrected JSON object. Return ONLY the "
                                "JSON, no commentary."
                            ),
                        }
                    ],
                },
            ]

    raise RuntimeError(f"extraction failed after {MAX_RETRIES + 1} attempts: {last_error}")


def run(corpus: Corpus, run: Run) -> None:  # noqa: A002 (intentional shadow of builtin)
    llm = LLM()
    system = _build_system_prompt()

    pdfs = corpus.pdfs()
    console.print(f"extracting from {len(pdfs)} PDFs with {llm.model}")

    successes: list[str] = []
    failures: list[tuple[str, str]] = []

    for pdf_path in pdfs:
        console.print(f"  • [cyan]{pdf_path.name}[/cyan]")
        try:
            paper, claims = _extract_one_paper(llm, system, pdf_path)
        except Exception as e:
            console.print(f"    [red]failed[/red]: {e}")
            failures.append((pdf_path.name, str(e)))
            continue

        _stamp_provenance(paper, claims, llm.model)
        # _validate_extraction already checked schemas + DAG, but provenance
        # stamping happens after, so re-validate to be safe.
        try:
            validate_paper(paper)
            for c in claims:
                validate_claim(c)
        except ValidationError as e:
            console.print(f"    [red]post-stamp validation failed[/red]: {e.message}")
            failures.append((pdf_path.name, f"post-stamp: {e.message}"))
            continue

        paper_id = paper["paper_id"]
        (run.papers_dir / f"{paper_id}.json").write_text(json.dumps(paper, indent=2))
        for c in claims:
            (run.claims_dir / _claim_filename(c["claim_id"])).write_text(
                json.dumps(c, indent=2)
            )
        successes.append(paper_id)
        console.print(f"    [green]→[/green] {paper_id} ({len(claims)} claims)")

    console.print()
    console.print(
        f"[bold]stage 1 summary[/bold]: "
        f"[green]{len(successes)} ok[/green], [red]{len(failures)} failed[/red]"
    )
    for name, err in failures:
        console.print(f"  [red]✗[/red] {name}: {err}")

    if not successes:
        raise RuntimeError("stage 1 produced no successful extractions")
