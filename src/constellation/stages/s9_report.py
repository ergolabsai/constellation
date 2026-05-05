"""Stage 9: write the human-readable synthesis.

Input:  the entire run directory (papers, claims, sheaf, ideas)
Output: run.report_path  (report.md)

PURE CODE — no LLM. The report renders:
  - Header + summary stats
  - Each Idea (label, description, scope, contributing claims, transitions, open Qs)
  - Research priorities (open questions aggregated across all Ideas, sorted by
    priority + effort — the "what to work on next" panel from the architecture)
  - Epsilon-machine complexity (C_mu + state distribution)
  - Pipeline diagnostics (MAP rewrites, residual H¹, Penrose triangles)
  - Pointers to the underlying JSON artifacts
"""
from __future__ import annotations

import json
from io import StringIO
from pathlib import Path

from rich.console import Console

from ..epsilon_machine import compute_epsilon_machine_metrics
from ..idea_partition import validate_idea_partition
from ..paths import Corpus, Run

console = Console()

PRIORITY_ORDER = {"high": 0, "medium": 1, "low": 2}
EFFORT_ORDER = {"low": 0, "medium": 1, "high": 2, "programmatic": 3}


# ---------- helpers ----------------------------------------------------------


def _load_artifacts(run: Run) -> dict:
    ideas = [
        json.loads(p.read_text()) for p in sorted(run.ideas_dir.glob("*.json"))
    ]
    epsilon_machine = (
        json.loads(run.epsilon_machine_path.read_text())
        if run.epsilon_machine_path.exists()
        else compute_epsilon_machine_metrics(ideas)
    )
    return {
        "sheaf": json.loads(run.sheaf_path.read_text()),
        "papers": [
            json.loads(p.read_text()) for p in sorted(run.papers_dir.glob("*.json"))
        ],
        "claims": {
            json.loads(p.read_text())["claim_id"]: json.loads(p.read_text())
            for p in sorted(run.claims_dir.glob("*.json"))
        },
        "ideas": ideas,
        "epsilon_machine": epsilon_machine,
    }


def _validate_artifacts(art: dict) -> None:
    """Preflight run artifacts before rendering a report."""
    selected_ids = set(art["sheaf"]["map_section"]["selected"].keys())
    validate_idea_partition(art["ideas"], selected_ids)


def _gather_priorities(ideas: list[dict]) -> list[dict]:
    """Flatten all open questions across Ideas, sorted by priority then effort."""
    rows = []
    for idea in ideas:
        for q in idea.get("open_questions", []) or []:
            for step in q.get("suggested_next_steps", []) or []:
                rows.append(
                    {
                        "idea_label": idea["label"],
                        "idea_id": idea["idea_id"],
                        "question": q["question"],
                        "priority": q.get("priority", "medium"),
                        "kind": step["kind"],
                        "description": step["description"],
                        "effort": step.get("effort", "medium"),
                        "maturity": step.get("maturity", "immediate"),
                        "expected_outcome": step.get("expected_outcome", ""),
                    }
                )
    rows.sort(
        key=lambda r: (
            PRIORITY_ORDER.get(r["priority"], 99),
            EFFORT_ORDER.get(r["effort"], 99),
        )
    )
    return rows


def _format_lambda(value: float) -> str:
    return f"{float(value):g}"


def _format_lambda_variant_groups(selections: list[dict]) -> str:
    groups: list[dict] = []
    for selection in selections:
        variant_id = selection["variant_id"]
        label = _format_lambda(selection["lambda_rewrite_penalty"])
        group = next((g for g in groups if g["variant_id"] == variant_id), None)
        if group is None:
            group = {"variant_id": variant_id, "lambdas": []}
            groups.append(group)
        group["lambdas"].append(label)

    return "; ".join(
        f"`{g['variant_id']}` at λ={', '.join(g['lambdas'])}" for g in groups
    )


# ---------- section writers --------------------------------------------------


def _write_header(buf: StringIO, corpus: Corpus, run: Run, sheaf: dict) -> None:
    buf.write(f"# Constellation report: {corpus.name}\n\n")
    buf.write(f"*Run: `{run.root.name}`*\n\n")
    ext = sheaf.get("extraction", {})
    ms = sheaf["map_section"]
    buf.write(
        f"**Model:** `{ext.get('model', 'unknown')}` · "
        f"**Pipeline:** `{sheaf.get('pipeline_version', 'v2_paper_as_stalk')}` · "
        f"**λ:** {ms['lambda_rewrite_penalty']}\n\n"
    )


def _write_summary(buf: StringIO, art: dict) -> None:
    sheaf = art["sheaf"]
    ms = sheaf["map_section"]
    f = sheaf.get("frustration", {})
    sensitivity = sheaf.get("lambda_sensitivity", {})
    machine = art.get("epsilon_machine", {})
    n_rewritten = ms.get("rewrite_cost", 0.0)  # treat any > 0 as nonzero
    n_rewrites = sum(
        1 for vid in ms["selected"].values() if not vid.endswith("#original")
    )
    n_residual = len(ms.get("residual_h1", []))
    n_sensitive = int(sensitivity.get("n_sensitive_claims", 0))
    n_stable = int(sensitivity.get("n_stable_claims", 0))

    buf.write("## Summary\n\n")
    buf.write(
        f"- **{len(art['papers'])} papers**, "
        f"**{len(art['claims'])} claims**, "
        f"**{len(sheaf['restriction_maps'])} comparability edges**, "
        f"**{len(art['ideas'])} Ideas**\n"
    )
    buf.write(
        f"- MAP coherence: **{ms['coherence']:+.2f}**, "
        f"rewrite cost: **{n_rewritten:.2f}** "
        f"({n_rewrites} of {len(ms['selected'])} claims rewritten)\n"
    )
    buf.write(
        f"- Residual H¹: **{n_residual} edge"
        f"{'s' if n_residual != 1 else ''}** unresolved\n"
    )
    if sensitivity:
        n_sweep_claims = n_sensitive + n_stable
        buf.write(
            f"- Lambda sensitivity: **{n_sensitive}/{n_sweep_claims} claims** "
            f"changed across {len(sensitivity.get('lambdas', []))} λ values\n"
        )
    if machine:
        buf.write(
            f"- ε-machine complexity: Cμ = "
            f"**{machine['statistical_complexity_bits']:.3f} bits**, "
            f"effective states = **{machine['effective_states']:.2f}**\n"
        )
    buf.write(
        f"- Frustration: ρ = **{f.get('rho', 0):.3f}** "
        f"({f.get('n_penrose', 0)} Penrose triangle"
        f"{'s' if f.get('n_penrose', 0) != 1 else ''} "
        f"out of {f.get('n_signed_triangles', 0)} signed)\n\n"
    )


def _write_idea_index(buf: StringIO, ideas: list[dict]) -> None:
    buf.write("## Consolidated theory\n\n")
    buf.write(f"The corpus consolidates into {len(ideas)} Ideas:\n\n")
    for i, idea in enumerate(ideas, 1):
        slug = idea["idea_id"].split("/")[-1]
        anchor = slug.replace("_", "-")
        buf.write(f"{i}. [{idea['label']}](#{anchor})\n")
    buf.write("\n---\n\n")


def _write_idea(buf: StringIO, idea: dict, claims: dict) -> None:
    buf.write(f"### {idea['label']}\n")
    buf.write(f"\n`{idea['idea_id']}`\n\n")
    buf.write(idea["description"] + "\n\n")

    s = idea["scope"]
    buf.write(f"**Scope.** _{s['generality']}_ — {s['framework']}.")
    if s.get("conditions"):
        buf.write(f" Conditions: {'; '.join(s['conditions'])}.")
    buf.write("\n\n")

    c = idea["consensus"]
    buf.write(
        f"**Consensus.** {c['n_claims']} claims from {c['n_papers_represented']} paper"
        f"{'s' if c['n_papers_represented'] != 1 else ''}; "
        f"mean credibility {c['mean_credibility']:.2f}; "
        f"agreement {c['agreement_score']:+.2f}. "
    )
    if c["n_rewritten"]:
        buf.write(
            f"{c['n_rewritten']} rewrite"
            f"{'s' if c['n_rewritten'] != 1 else ''} "
            f"(total cost {c['total_rewrite_cost']:.2f}).\n\n"
        )
    else:
        buf.write("All originals.\n\n")

    f = idea["frustration"]
    if f["n_penrose"] > 0 or f["residual_negative_edges"]:
        buf.write(
            f"**Frustration.** ρ = {f['rho']:.2f}, "
            f"{f['n_penrose']} intra-Idea Penrose triangle"
            f"{'s' if f['n_penrose'] != 1 else ''}, "
            f"{len(f['residual_negative_edges'])} residual negative edge"
            f"{'s' if len(f['residual_negative_edges']) != 1 else ''}.\n\n"
        )

    buf.write("**Contributing claims** (sorted by credibility):\n\n")
    for cc in idea["contributing_claims"]:
        rewritten = not cc["selected_variant_id"].endswith("#original")
        marker = " *(rewritten)*" if rewritten else ""
        claim = claims.get(cc["claim_id"], {})
        short = (claim.get("cause") or "").strip()[:90]
        buf.write(
            f"- `{cc['claim_id']}` "
            f"[{cc['role_in_idea']}, cred {cc['credibility']:.2f}]{marker}\n"
            f"  - {short}\n"
        )
    buf.write("\n")

    if idea["transitions_out"]:
        buf.write("**Transitions out:**\n\n")
        for t in idea["transitions_out"]:
            target_short = t["to_idea_id"].split("/")[-1]
            buf.write(
                f"- → `{target_short}` ({t['kind']})"
                + (f" — {t['note']}" if t.get("note") else "")
                + "\n"
            )
        buf.write("\n")
    if idea["transitions_in"]:
        buf.write("**Transitions in:**\n\n")
        for t in idea["transitions_in"]:
            source_short = t["from_idea_id"].split("/")[-1]
            buf.write(
                f"- ← `{source_short}` ({t['kind']})"
                + (f" — {t['note']}" if t.get("note") else "")
                + "\n"
            )
        buf.write("\n")

    if idea["open_questions"]:
        buf.write(f"**Open questions** ({len(idea['open_questions'])}):\n\n")
        for q in idea["open_questions"]:
            buf.write(
                f"> *{q['question']}* — priority {q.get('priority', 'medium')}\n\n"
            )
            for step in q.get("suggested_next_steps", []):
                buf.write(
                    f"  - **{step['kind']}** "
                    f"({step.get('effort', '?')} / {step.get('maturity', '?')}): "
                    f"{step['description']}\n"
                )
                if step.get("expected_outcome"):
                    buf.write(f"    - *Expected:* {step['expected_outcome']}\n")
        buf.write("\n")

    buf.write("---\n\n")


def _write_priorities(buf: StringIO, ideas: list[dict]) -> None:
    rows = _gather_priorities(ideas)
    if not rows:
        return
    buf.write("## Research priorities\n\n")
    buf.write(
        "Open-question next-steps across all Ideas, sorted by priority "
        "then effort. The fastest wins (low-effort + immediate maturity) "
        "appear first.\n\n"
    )
    by_kind: dict[str, list[dict]] = {}
    for r in rows:
        by_kind.setdefault(r["kind"], []).append(r)
    for kind in (
        "experiment",
        "simulation",
        "theoretical_development",
        "code_capability",
        "instrumentation",
        "further_extraction",
        "literature_review",
    ):
        kind_rows = by_kind.get(kind, [])
        if not kind_rows:
            continue
        buf.write(f"### {kind.replace('_', ' ').title()} ({len(kind_rows)})\n\n")
        for r in kind_rows:
            buf.write(
                f"- **[{r['priority']}/{r['effort']}]** {r['description']}\n"
                f"  - *From:* {r['idea_label'][:70]}\n"
                f"  - *Question:* {r['question']}\n"
            )
            if r["expected_outcome"]:
                buf.write(f"  - *Expected:* {r['expected_outcome']}\n")
        buf.write("\n")


def _write_lambda_sensitivity(buf: StringIO, sheaf: dict) -> None:
    sensitivity = sheaf.get("lambda_sensitivity")
    if not sensitivity:
        return

    lambdas = sensitivity.get("lambdas", [])
    sensitive_claims = sensitivity.get("sensitive_claims", [])
    n_sensitive = int(sensitivity.get("n_sensitive_claims", 0))
    n_stable = int(sensitivity.get("n_stable_claims", 0))
    n_total = n_sensitive + n_stable

    buf.write("### Lambda sensitivity\n\n")
    if lambdas:
        sweep = ", ".join(f"λ={_format_lambda(lam)}" for lam in lambdas)
        buf.write(f"Sweep: {sweep}\n\n")
    buf.write(f"- Sensitive claims: **{n_sensitive}/{n_total}**\n")

    sections = sensitivity.get("sections", [])
    if sections:
        buf.write("- Winning sections:\n")
        for section in sections:
            buf.write(
                f"  - λ={_format_lambda(section['lambda_rewrite_penalty'])}: "
                f"total {section['total_score']:+.2f}, "
                f"coherence {section['coherence']:+.2f}, "
                f"rewrite cost {section['rewrite_cost']:.2f}, "
                f"{section.get('n_rewritten', 0)} rewritten\n"
            )
    buf.write("\n")

    if sensitive_claims:
        buf.write("Claims whose selected variant changes across λ:\n\n")
        for row in sensitive_claims[:10]:
            groups = _format_lambda_variant_groups(row["selections_by_lambda"])
            buf.write(f"- `{row['claim_id']}`: {groups}\n")
        if len(sensitive_claims) > 10:
            buf.write(f"- … {len(sensitive_claims) - 10} more\n")
        buf.write("\n")
    else:
        buf.write("All claim selections are stable across the sweep.\n\n")


def _write_epsilon_machine(buf: StringIO, machine: dict) -> None:
    if not machine:
        return

    buf.write("## ε-machine complexity\n\n")
    buf.write(
        f"Cμ = **{machine['statistical_complexity_bits']:.3f} bits** "
        f"({machine['normalized_statistical_complexity']:.0%} of maximum); "
        f"effective states = **{machine['effective_states']:.2f}** "
        f"across {machine['n_states']} Ideas and {machine['n_claims']} claims.\n\n"
    )
    graph = machine["transition_graph"]
    buf.write(
        f"Transitions: **{graph['n_unique_transition_pairs']}** directed Idea pairs "
        f"({graph['transition_density']:.0%} density), "
        f"{graph['n_transitions']} labeled transition"
        f"{'s' if graph['n_transitions'] != 1 else ''}.\n\n"
    )

    buf.write("State distribution:\n\n")
    for state in machine["state_distribution"]:
        buf.write(
            f"- `{state['idea_id']}`: p={state['probability']:.3f}, "
            f"{state['n_claims']} claim"
            f"{'s' if state['n_claims'] != 1 else ''}, "
            f"{state['transitions_out']} out / {state['transitions_in']} in\n"
        )
    buf.write("\n")


def _write_diagnostics(buf: StringIO, sheaf: dict) -> None:
    buf.write("## Pipeline diagnostics\n\n")

    _write_lambda_sensitivity(buf, sheaf)

    # MAP rewrites
    selected = sheaf["map_section"]["selected"]
    rewrites = [
        (cid, vid) for cid, vid in selected.items() if not vid.endswith("#original")
    ]
    if rewrites:
        buf.write(f"### Claims rewritten by MAP ({len(rewrites)})\n\n")
        for cid, vid in sorted(rewrites):
            variant = next(
                v
                for v in sheaf["stalks"][cid]["variants"]
                if v["variant_id"] == vid
            )
            descriptor = vid.split("#", 1)[1]
            buf.write(
                f"- `{cid}` → `#{descriptor}` "
                f"(rewrite distance {variant['rewrite_distance']:.2f})\n"
            )
            if variant.get("targets"):
                buf.write(
                    f"  - *Targets:* {', '.join(variant['targets'])}\n"
                )
            if variant.get("evidence_weaknesses_invoked"):
                weaknesses = variant["evidence_weaknesses_invoked"]
                buf.write(
                    f"  - *Weaknesses invoked:* {len(weaknesses)} "
                    f"(e.g. \"{weaknesses[0][:120]}\")\n"
                )
        buf.write("\n")

    # Residual H¹
    residual = sheaf["map_section"].get("residual_h1", [])
    if residual:
        buf.write(
            f"### Residual H¹ — unresolved obstructions ({len(residual)})\n\n"
        )
        for r in residual:
            buf.write(
                f"- `{r['edge_id']}` (selected score {r['selected_score']:+.2f})\n"
                f"  - {r['why_unresolved']}\n"
            )
        buf.write("\n")

    # Penrose triangles
    f = sheaf.get("frustration", {})
    pens = f.get("penrose_triangles", [])
    if pens:
        buf.write(
            f"### Penrose triangles — frustrated 3-claim configurations "
            f"({len(pens)})\n\n"
        )
        for tri in pens:
            buf.write(
                "- " + " — ".join(f"`{c}`" for c in tri) + "\n"
            )
        buf.write("\n")


def _write_artifacts_pointer(buf: StringIO, run: Run, art: dict) -> None:
    buf.write("## Artifacts\n\n")
    n_p = len(art["papers"])
    n_c = len(art["claims"])
    n_i = len(art["ideas"])
    buf.write(f"All in `{run.root.name}/`:\n\n")
    buf.write(
        "- `run_config.json` — model, schema, prompt hash, and parameter snapshot\n"
    )
    if run.failures_path.exists():
        buf.write("- `failures.json` — structured stage failures, if any\n")
    if run.epsilon_machine_path.exists():
        buf.write("- `epsilon_machine.json` — ε-machine Cμ and transition metrics\n")
    buf.write(f"- `papers/` — {n_p} paper records\n")
    buf.write(f"- `claims/` — {n_c} claim records\n")
    buf.write("- `tag_vocabulary.json` — semilattice + SNAG vocabulary\n")
    buf.write("- `tags.json` — per-claim tags\n")
    buf.write("- `comparability_complex.json` — stage-3 edge list\n")
    buf.write(
        "- `sheaf.json` — full sheaf (stalks, restriction maps, MAP, "
        "lambda sensitivity, frustration)\n"
    )
    buf.write(f"- `ideas/` — {n_i} consolidated knowledge units\n")
    buf.write("- `llm_cache/` — successful validated LLM JSON responses\n")


# ---------- orchestration ----------------------------------------------------


def run(corpus: Corpus, run: Run) -> None:  # noqa: A002 (intentional shadow)
    if not run.sheaf_path.exists():
        raise RuntimeError(
            f"missing sheaf.json under {run.root}; run earlier stages first"
        )
    if not list(run.ideas_dir.glob("*.json")):
        raise RuntimeError(
            f"no ideas found under {run.ideas_dir}; run stage 8 first"
        )

    art = _load_artifacts(run)
    _validate_artifacts(art)

    buf = StringIO()
    _write_header(buf, corpus, run, art["sheaf"])
    _write_summary(buf, art)
    _write_idea_index(buf, art["ideas"])
    for idea in art["ideas"]:
        _write_idea(buf, idea, art["claims"])
    _write_priorities(buf, art["ideas"])
    _write_epsilon_machine(buf, art["epsilon_machine"])
    _write_diagnostics(buf, art["sheaf"])
    _write_artifacts_pointer(buf, run, art)

    text = buf.getvalue()
    run.report_path.write_text(text)

    n_lines = text.count("\n")
    try:
        rel = run.report_path.relative_to(Path.cwd())
    except ValueError:
        rel = run.report_path
    console.print(
        f"  wrote [bold]{rel}[/bold]  "
        f"({len(text):,} chars, {n_lines:,} lines)"
    )
