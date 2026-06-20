from __future__ import annotations

import html
import json
from pathlib import Path

from .util import Json


def write_report(run_dir: Path, papers: list[Json], claims: list[Json], evidence: list[Json], sheaf: Json, ideas: list[Json]) -> None:
    semantic_count = len(sheaf.get("semantic_edge_ids") or [])
    incoming = sheaf.get("incoming_paper_ids") or []
    lambda_model = sheaf["objective"].get("lambda_model", "flat")
    lines = [
        "# Constellation Report",
        "",
        f"- Papers: {len(papers)}",
        f"- Claims: {len(claims)}",
        f"- Evidence pieces: {len(evidence)}",
        f"- Claim-evidence edges: {len(sheaf['edges'])} "
        f"({semantic_count} from semantic cross-paper propagation)",
        f"- Cost model: `{lambda_model}`"
        + (f" (incoming paper(s): {', '.join(f'`{p}`' for p in incoming)})" if incoming else ""),
        f"- Initial residual: {sheaf['objective']['initial_residual']:.3f}",
        f"- Final residual: {sheaf['objective']['final_residual']:.3f}",
        f"- Claim rewrite distance: {sheaf['objective']['claim_rewrite_distance']:.3f}",
        "",
        "## Rewrites",
        "",
    ]
    if sheaf["operations"]:
        for op in sheaf["operations"]:
            lam = op.get("lambda")
            lam_note = f"; lambda={lam:.2f}" if lam is not None else ""
            lines.append(
                f"- `{op['claim_id']}`: `{op['from']}` -> `{op['to']}`; "
                f"residual {op['initial_residual']:.3f} -> {op['final_residual']:.3f}"
                f"{lam_note}"
            )
    else:
        lines.append("- No claim rewrites were accepted.")

    stature = sheaf.get("stature") or {}
    hygiene = sheaf.get("claim_hygiene") or {}
    by_status: dict[str, list[str]] = {}
    for cid, info in hygiene.items():
        by_status.setdefault(info.get("status", "not_applicable"), []).append(cid)
    implicit = sorted(by_status.get("implicit_headline", []))
    consensus = sorted(by_status.get("consensus_aligned", []))
    scoped = sorted(by_status.get("scoped_explicit", []))
    if stature or hygiene:
        lines.extend(["", "## Map state", ""])
        if stature:
            top = sorted(stature.items(), key=lambda kv: (-kv[1], kv[0]))[:8]
            top_str = ", ".join(f"`{cid}` ({n})" for cid, n in top)
            lines.append(f"- Highest stature claims (independent backing papers): {top_str}")
        if implicit:
            lines.append(
                "- Implicit-headline claims (propagation contradicts comparable "
                "evidence; structural suspects): "
                f"{', '.join(f'`{c}`' for c in implicit)}"
            )
        if consensus:
            lines.append(
                "- Consensus-aligned claims (propagation agrees with the rest of "
                f"the field): {', '.join(f'`{c}`' for c in consensus)}"
            )
        if scoped:
            lines.append(
                "- Scope-aware claims (explicit predictions cover the comparability "
                f"group): {', '.join(f'`{c}`' for c in scoped)}"
            )

    lines.extend(["", "## Subjects", ""])
    for subject in ideas:
        lines.append(f"### {subject['title']}")
        if subject.get("description"):
            lines.append("")
            lines.append(f"_{subject['description']}_")
        lines.append("")
        subject_ideas = subject.get("ideas") or []
        if not subject_ideas:
            lines.append(f"- _No ideas yet (ungrouped subject)._")
            if subject.get("contributing_evidence"):
                lines.append(
                    f"- Evidence: {', '.join(f'`{e}`' for e in subject['contributing_evidence'])}"
                )
            lines.append("")
            continue
        counts = {"novel": 0, "contested": 0, "established": 0}
        for idea in subject_ideas:
            counts[idea.get("status", "established")] = counts.get(idea.get("status", "established"), 0) + 1
        lines.append(
            f"_{counts['established']} established · "
            f"{counts['contested']} contested · "
            f"{counts['novel']} novel_"
        )
        lines.append("")
        for i_idx, idea in enumerate(subject_ideas, 1):
            status = idea.get("status", "established").upper()
            lines.append(f"**Idea {i_idx} [{status}]: {idea['title']}**")
            claims_list = sorted(idea["contributing_claims"])
            marked = [
                f"`{c}` [implicit-headline]" if c in implicit else f"`{c}`"
                for c in claims_list
            ]
            lines.append(f"- Papers: `{idea['contributing_papers'][0]}`  ·  Claims: {', '.join(marked)}")
            scope = idea.get("scope") or {}
            if scope.get("keywords"):
                lines.append(f"- Scope.keywords: {', '.join(scope['keywords'])}")
            if idea.get("supporting_evidence"):
                lines.append(
                    f"- Supporting evidence: {', '.join(f'`{e}`' for e in idea['supporting_evidence'])}"
                )
            if idea.get("contesting_evidence"):
                lines.append(
                    f"- Contesting evidence: {', '.join(f'`{e}`' for e in idea['contesting_evidence'])}"
                )
            if idea.get("contests"):
                contest_lines = []
                for c in idea["contests"]:
                    contest_lines.append(
                        f"`{c['idea_id']}` ({', '.join(c['papers'])}) at "
                        f"{', '.join(f'`{e}`' for e in c['at'])}"
                    )
                lines.append(f"- Contests: {'; '.join(contest_lines)}")
            if idea.get("supports"):
                support_papers = sorted({
                    p for s in idea["supports"] for p in s["papers"]
                })
                lines.append(
                    f"- Supported by: {', '.join(f'`{p}`' for p in support_papers)}"
                )
            if idea.get("next_steps"):
                lines.append("- Next steps:")
                for step in idea["next_steps"]:
                    lines.append(f"  - **{step['kind']}** — {step['title']}: {step['description']}")
            lines.append("")

    run_dir.joinpath("report.md").write_text("\n".join(lines))
    write_html(run_dir, sheaf, ideas)


def write_html(run_dir: Path, sheaf: Json, ideas: list[Json]) -> None:
    claims = [
        json.loads(path.read_text())
        for path in sorted((run_dir / "claims").glob("*.json"))
    ]
    evidence = [
        json.loads(path.read_text())
        for path in sorted((run_dir / "evidence").glob("*.json"))
    ]
    papers = [
        json.loads(path.read_text())
        for path in sorted((run_dir / "papers").glob("*.json"))
    ]
    data = _viz_data(papers, claims, evidence, sheaf, ideas)
    data_json = json.dumps(data, ensure_ascii=True, separators=(",", ":"))
    report_title = html.escape(_report_title(sheaf))
    doc = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{report_title}</title>
  <style>
    :root {{
      --bg: #f8fafc;
      --panel: #ffffff;
      --border: #dbe2ea;
      --text: #172033;
      --muted: #64748b;
      --accent: #2563eb;
      --warn: #d97706;
      --bad: #dc2626;
      --ok: #16a34a;
      --shadow: 0 12px 30px rgba(15, 23, 42, 0.08);
    }}
    * {{ box-sizing: border-box; }}
    html, body {{ height: 100%; margin: 0; }}
    body {{
      font-family: ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      color: var(--text);
      background: var(--bg);
      font-size: 13px;
      line-height: 1.4;
      overflow: hidden;
    }}
    header {{
      height: 58px;
      padding: 10px 16px;
      border-bottom: 1px solid var(--border);
      background: var(--panel);
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 14px;
    }}
    h1 {{ margin: 0; font-size: 16px; font-weight: 700; }}
    h2 {{
      margin: 16px 0 8px;
      color: var(--muted);
      font-size: 11px;
      font-weight: 800;
      letter-spacing: 0;
      text-transform: uppercase;
    }}
    h3 {{ margin: 0 0 6px; font-size: 14px; line-height: 1.25; }}
    button {{
      border: 1px solid var(--border);
      background: white;
      color: var(--text);
      border-radius: 6px;
      padding: 6px 9px;
      font: inherit;
      cursor: pointer;
    }}
    button:hover {{ border-color: #94a3b8; background: #f8fafc; }}
    .meta {{ color: var(--muted); display: flex; flex-wrap: wrap; gap: 10px; justify-content: flex-end; }}
    .meta b {{ color: var(--text); }}
    main {{
      display: grid;
      grid-template-columns: minmax(0, 1fr) 430px;
      height: calc(100vh - 58px);
      min-height: 0;
    }}
    #stage {{ position: relative; min-height: 0; overflow: hidden; }}
    #graph-svg {{ width: 100%; height: 100%; display: block; background: var(--bg); cursor: grab; }}
    #graph-svg:active {{ cursor: grabbing; }}
    #side {{
      border-left: 1px solid var(--border);
      background: var(--panel);
      min-height: 0;
      overflow-y: auto;
      padding: 14px 16px 20px;
    }}
    .toolbar {{
      position: absolute;
      left: 12px;
      top: 12px;
      z-index: 10;
      display: flex;
      gap: 6px;
      padding: 6px;
      border: 1px solid var(--border);
      border-radius: 8px;
      background: rgba(255, 255, 255, 0.92);
      box-shadow: var(--shadow);
      backdrop-filter: blur(8px);
    }}
    .status-indicator {{
      position: absolute;
      right: 12px;
      top: 12px;
      z-index: 10;
      font: 11px ui-monospace, SFMono-Regular, Menlo, monospace;
      color: var(--muted);
      padding: 6px 10px;
      border: 1px solid var(--border);
      border-radius: 6px;
      background: rgba(255, 255, 255, 0.92);
      pointer-events: none;
    }}
    .tooltip {{
      position: absolute;
      pointer-events: none;
      opacity: 0;
      max-width: 300px;
      background: #111827;
      color: white;
      border-radius: 6px;
      padding: 8px 10px;
      font-size: 12px;
      line-height: 1.35;
      box-shadow: var(--shadow);
      z-index: 4;
    }}
    .tooltip .id {{ color: #93c5fd; font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 11px; }}
    .edge {{
      fill: none;
      stroke-linecap: round;
      transition: opacity 160ms, stroke-width 160ms;
    }}
    .edge.zero {{ stroke: #cbd5e1; stroke-width: 1.25; opacity: 0.72; }}
    .edge.tiny {{ stroke: #94a3b8; stroke-width: 1.5; opacity: 0.78; }}
    .edge.mild {{ stroke: var(--warn); stroke-width: 2.6; opacity: 0.9; }}
    .edge.high {{ stroke: var(--bad); stroke-width: 3.2; opacity: 0.95; }}
    .edge.semantic {{ stroke-dasharray: 5 3; }}
    .edge.dimmed, .node.dimmed, .label.dimmed, .idea-hull.dimmed, .idea-label.dimmed,
    .assertion-hull.dimmed, .assertion-label.dimmed {{ opacity: 0.12; }}
    .idea-hull {{
      fill-opacity: 0.14;
      stroke-opacity: 0.72;
      stroke-width: 1.4;
      stroke-linejoin: round;
      cursor: pointer;
      transition: opacity 160ms, fill-opacity 160ms, stroke-width 160ms;
    }}
    .idea-hull.focused {{ fill-opacity: 0.24; stroke-width: 3; }}
    .assertion-hull {{
      fill-opacity: 0.16;
      stroke-opacity: 0.85;
      stroke-width: 1.6;
      stroke-linejoin: round;
      stroke-dasharray: 5 3;
      pointer-events: none;
      opacity: 0;
      transition: opacity 180ms;
    }}
    .assertion-hull.expanded {{ opacity: 1; pointer-events: auto; cursor: pointer; }}
    .assertion-hull.inner-focused {{ fill-opacity: 0.32; stroke-width: 2.6; }}
    .assertion-hull.inner-dimmed {{ opacity: 0.18; }}
    .assertion-hull.established {{ fill: var(--ok); stroke: var(--ok); }}
    .assertion-hull.contested {{ fill: var(--bad); stroke: var(--bad); }}
    .assertion-hull.novel {{ fill: var(--accent); stroke: var(--accent); }}
    .assertion-label {{
      pointer-events: none;
      font-size: 9.5px;
      font-weight: 800;
      paint-order: stroke;
      stroke: white;
      stroke-width: 4px;
      stroke-linejoin: round;
      letter-spacing: 0.4px;
      opacity: 0;
      transition: opacity 180ms;
    }}
    .assertion-label.expanded {{ opacity: 1; }}
    .assertion-label.established {{ fill: var(--ok); }}
    .assertion-label.contested {{ fill: var(--bad); }}
    .assertion-label.novel {{ fill: var(--accent); }}
    .idea-label {{
      pointer-events: none;
      font-size: 11px;
      font-weight: 800;
      fill: #0f172a;
      paint-order: stroke;
      stroke: white;
      stroke-width: 4px;
      stroke-linejoin: round;
    }}
    .node {{ cursor: pointer; transition: opacity 160ms; }}
    .node .shape {{ stroke: white; stroke-width: 1.7; }}
    .node.kumar .shape {{ stroke: #facc15; stroke-width: 2.8; }}
    .node.rewritten .shape {{
      stroke: var(--accent);
      stroke-width: 3;
      stroke-dasharray: 4 2;
    }}
    .node.context-filled .shape {{
      stroke: var(--warn);
      stroke-width: 3;
      stroke-dasharray: 4 2;
    }}
    .node.selected .shape {{
      stroke: #0f172a;
      stroke-width: 4;
      stroke-dasharray: none;
    }}
    .label {{
      pointer-events: none;
      font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
      font-size: 10px;
      font-weight: 700;
      fill: #1e293b;
      text-anchor: middle;
      paint-order: stroke;
      stroke: white;
      stroke-width: 3px;
      stroke-linejoin: round;
    }}
    .legend-card {{
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 9px 10px;
      margin: 6px 0;
      background: white;
      cursor: pointer;
      transition: border 120ms, background 120ms, transform 120ms;
      overflow-wrap: anywhere;
      word-break: break-word;
    }}
    .legend-card:hover {{ background: #f8fafc; transform: translateY(-1px); }}
    .legend-card.active {{ border-color: var(--accent); box-shadow: inset 3px 0 0 var(--accent); }}
    .legend-row {{ display: flex; gap: 8px; align-items: flex-start; }}
    .swatch {{ flex: 0 0 14px; width: 14px; height: 14px; border-radius: 4px; margin-top: 2px; }}
    .legend-title {{ font-weight: 700; font-size: 12px; line-height: 1.25; }}
    .legend-sub {{ color: var(--muted); font-size: 11px; margin-top: 2px; }}
    .legend-card > .legend-row > div {{ min-width: 0; flex: 1; }}
    .paper-row {{ display: flex; align-items: center; gap: 7px; font-size: 12px; margin: 5px 0; }}
    .paper-dot {{ width: 10px; height: 10px; border-radius: 50%; flex: 0 0 10px; }}
    .shape-legend, .edge-legend {{ display: grid; gap: 7px; }}
    .shape-line, .edge-line {{ display: flex; align-items: center; gap: 8px; color: var(--muted); }}
    .shape-line b, .edge-line b {{ color: var(--text); }}
    .detail {{ margin-top: 12px; padding-top: 12px; border-top: 1px solid var(--border); }}
    .detail p {{ margin: 6px 0; }}
    .pill-row {{ display: flex; flex-wrap: wrap; gap: 4px; margin: 7px 0; }}
    .pill {{
      display: inline-flex;
      align-items: center;
      min-height: 22px;
      max-width: 100%;
      padding: 3px 7px;
      border-radius: 999px;
      color: white;
      font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
      font-size: 10.5px;
      font-weight: 700;
      overflow-wrap: anywhere;
      cursor: pointer;
    }}
    .callout {{
      border-left: 3px solid var(--accent);
      background: #eff6ff;
      padding: 8px 10px;
      border-radius: 0 6px 6px 0;
      margin: 7px 0;
      overflow-wrap: anywhere;
      word-break: break-word;
      max-height: 240px;
      overflow-y: auto;
      cursor: zoom-in;
      transition: max-height 200ms;
    }}
    .callout.expanded {{ max-height: none; cursor: zoom-out; }}
    .callout.warn {{ border-left-color: var(--warn); background: #fff7ed; }}
    .callout.bad {{ border-left-color: var(--bad); background: #fef2f2; }}
    .callout.question.blocking {{ border-left-color: var(--bad); background: #fef2f2; }}
    .callout.question.high {{ border-left-color: var(--warn); background: #fff7ed; }}
    .callout.question.medium {{ border-left-color: var(--accent); background: #eff6ff; }}
    .callout.question.exploratory {{ border-left-color: var(--ok); background: #f0fdf4; }}
    .callout .k {{ color: var(--muted); font-size: 11px; font-weight: 700; }}
    .priority {{
      display: inline-flex;
      align-items: center;
      min-height: 18px;
      padding: 1px 6px;
      margin-right: 6px;
      border-radius: 999px;
      font-size: 10px;
      font-weight: 800;
      text-transform: uppercase;
    }}
    .priority.blocking {{ background: #fee2e2; color: #991b1b; }}
    .priority.high {{ background: #ffedd5; color: #9a3412; }}
    .priority.medium {{ background: #dbeafe; color: #1d4ed8; }}
    .priority.exploratory {{ background: #dcfce7; color: #166534; }}
    .next-work {{
      margin-top: 8px;
      display: grid;
      gap: 6px;
    }}
    .next-step {{
      border: 1px solid var(--border);
      border-left: 3px solid var(--accent);
      border-radius: 6px;
      background: white;
      padding: 7px 8px;
    }}
    .next-step .kind {{
      display: inline-flex;
      align-items: center;
      min-height: 18px;
      padding: 1px 6px;
      border-radius: 999px;
      background: #e0f2fe;
      color: #075985;
      font-size: 10px;
      font-weight: 800;
      text-transform: uppercase;
    }}
    .next-step .title {{ margin-left: 6px; font-weight: 750; }}
    .next-step .desc {{ margin-top: 4px; color: var(--muted); font-size: 11.5px; }}
    .muted {{ color: var(--muted); }}
    .mono {{ font-family: ui-monospace, SFMono-Regular, Menlo, monospace; }}
    .score-grid {{
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 8px;
      margin-top: 8px;
    }}
    .score {{
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 8px;
      background: #fbfdff;
    }}
    .score .v {{ font-size: 18px; font-weight: 800; }}
    .score .k {{ color: var(--muted); font-size: 11px; }}
    @media (max-width: 920px) {{
      body {{ overflow: auto; }}
      header {{ height: auto; align-items: flex-start; }}
      main {{ display: block; height: auto; }}
      #stage {{ height: 68vh; min-height: 520px; }}
      #side {{ border-left: 0; border-top: 1px solid var(--border); }}
    }}
  </style>
</head>
<body>
  <header>
    <div>
      <h1>{report_title}</h1>
      <div class="muted">Bipartite claim/evidence sheaf with residual-aware rewrites</div>
    </div>
    <div class="meta" id="meta"></div>
  </header>
  <main>
    <section id="stage">
      <svg id="graph-svg" role="img" aria-label="Claim and evidence constellation"></svg>
      <div class="toolbar">
        <button id="zoom-out-btn" type="button" title="Zoom out" onclick="window.stepZoom && window.stepZoom(0.8);">−</button>
        <button id="zoom-in-btn" type="button" title="Zoom in" onclick="window.stepZoom && window.stepZoom(1.25);">+</button>
        <button id="fit-btn" type="button" title="Fit graph" onclick="window.fitGraph && window.fitGraph(true);">Fit</button>
        <button id="clear-btn" type="button" title="Clear focus" onclick="window.clearFocus && window.clearFocus();">Clear</button>
      </div>
      <div class="status-indicator" id="status-indicator">init…</div>
      <div class="tooltip" id="tooltip"></div>
    </section>
    <aside id="side">
      <h2>Legend</h2>
      <div class="shape-legend">
        <div class="shape-line">
          <svg width="22" height="22" viewBox="-12 -12 24 24"><circle r="9" fill="#64748b" stroke="white" stroke-width="2"/></svg>
          <span><b>claim</b> circle, dashed when rewritten</span>
        </div>
        <div class="shape-line">
          <svg width="22" height="22" viewBox="-14 -14 28 28"><path d="M 0,-12 L 3.4,-4 L 12,-4 L 5.2,1.8 L 7.4,11 L 0,6 L -7.4,11 L -5.2,1.8 L -12,-4 L -3.4,-4 Z" fill="#eab308" stroke="#facc15" stroke-width="2"/></svg>
          <span><b>Kumar claim</b> star</span>
        </div>
        <div class="shape-line">
          <svg width="22" height="22" viewBox="-12 -12 24 24"><rect x="-9" y="-9" width="18" height="18" rx="2" fill="#64748b" stroke="white" stroke-width="2"/></svg>
          <span><b>evidence</b> square, dashed when context-filled</span>
        </div>
        <div class="shape-line">
          <svg width="22" height="22" viewBox="-14 -14 28 28"><path d="M 0,-12 L 12,0 L 0,12 L -12,0 Z" fill="#eab308" stroke="#facc15" stroke-width="2"/></svg>
          <span><b>Kumar evidence</b> diamond</span>
        </div>
      </div>
      <h2>Edges</h2>
      <div class="edge-legend">
        <div class="edge-line"><svg width="42" height="12"><line x1="2" y1="6" x2="40" y2="6" stroke="#cbd5e1" stroke-width="2"/></svg><span><b>agreement</b> residual near 0</span></div>
        <div class="edge-line"><svg width="42" height="12"><line x1="2" y1="6" x2="40" y2="6" stroke="#d97706" stroke-width="3"/></svg><span><b>mild tension</b> residual below 0.5</span></div>
        <div class="edge-line"><svg width="42" height="12"><line x1="2" y1="6" x2="40" y2="6" stroke="#dc2626" stroke-width="4"/></svg><span><b>strong tension</b> residual 0.5 or above</span></div>
        <div class="edge-line"><svg width="42" height="12"><line x1="2" y1="6" x2="40" y2="6" stroke="#475569" stroke-width="2" stroke-dasharray="5 3"/></svg><span><b>semantic</b> cross-paper propagation</span></div>
      </div>
      <h2>Ideas (visible when a subject is selected)</h2>
      <div class="edge-legend">
        <div class="edge-line"><svg width="42" height="14"><rect x="2" y="2" width="38" height="10" fill="#16a34a" fill-opacity="0.18" stroke="#16a34a" stroke-width="1.6" stroke-dasharray="5 3" rx="2"/></svg><span><b>established</b> backed and uncontested</span></div>
        <div class="edge-line"><svg width="42" height="14"><rect x="2" y="2" width="38" height="10" fill="#dc2626" fill-opacity="0.18" stroke="#dc2626" stroke-width="1.6" stroke-dasharray="5 3" rx="2"/></svg><span><b>contested</b> contradicts another idea</span></div>
        <div class="edge-line"><svg width="42" height="14"><rect x="2" y="2" width="38" height="10" fill="#2563eb" fill-opacity="0.18" stroke="#2563eb" stroke-width="1.6" stroke-dasharray="5 3" rx="2"/></svg><span><b>novel</b> incoming, awaits replication</span></div>
      </div>
      <div class="score-grid" id="score-grid"></div>
      <h2>Papers</h2>
      <div id="papers"></div>
      <h2>Subjects</h2>
      <div class="muted" style="font-size: 11px; margin-bottom: 6px;">Click a subject to expand its ideas.</div>
      <div id="ideas"></div>
      <div id="detail" class="detail"></div>
    </aside>
  </main>
  <script>
const DATA = {data_json};

const SVG_NS = "http://www.w3.org/2000/svg";
const svg = document.getElementById("graph-svg");
const tooltip = document.getElementById("tooltip");
const state = {{ focusType: null, focusId: null, innerIdeaId: null, scale: 1, tx: 0, ty: 0 }};
const nodeById = Object.fromEntries([...DATA.claims, ...DATA.evidence].map(n => [n.id, n]));
const ideaById = Object.fromEntries(DATA.ideas.map(i => [i.id, i]));
const edgesByNode = Object.fromEntries(Object.keys(nodeById).map(id => [id, []]));
const STAR_PATH = "M 0,-12 L 3.4,-4 L 12,-4 L 5.2,1.8 L 7.4,11 L 0,6 L -7.4,11 L -5.2,1.8 L -12,-4 L -3.4,-4 Z";
const DIAMOND_PATH = "M 0,-12 L 12,0 L 0,12 L -12,0 Z";
for (const edge of DATA.edges) {{
  edgesByNode[edge.source].push(edge);
  edgesByNode[edge.target].push(edge);
}}

const layers = {{
  root: el("g"),
  hulls: el("g"),
  assertionHulls: el("g"),
  edges: el("g"),
  nodes: el("g"),
  labels: el("g"),
  ideaLabels: el("g"),
  assertionLabels: el("g"),
}};
svg.appendChild(layers.root);
layers.root.append(
  layers.hulls,
  layers.assertionHulls,
  layers.edges,
  layers.nodes,
  layers.labels,
  layers.ideaLabels,
  layers.assertionLabels,
);

function el(name, attrs={{}}) {{
  const node = document.createElementNS(SVG_NS, name);
  for (const [key, value] of Object.entries(attrs)) node.setAttribute(key, String(value));
  return node;
}}

function escapeHtml(value) {{
  const map = {{"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}};
  return String(value ?? "").replace(/[&<>"']/g, ch => map[ch]);
}}

function metric(value) {{
  return Number(value).toFixed(3).replace(/\\.000$/, "");
}}

function showInitError(err) {{
  console.error("constellation init error:", err);
  const banner = document.createElement("div");
  banner.style.cssText = "position:fixed;top:0;left:0;right:0;background:#fef2f2;border-bottom:2px solid #dc2626;color:#991b1b;padding:8px 14px;font:13px ui-monospace,SFMono-Regular,Menlo,monospace;z-index:999;white-space:pre-wrap;max-height:40vh;overflow:auto;";
  banner.textContent = "Constellation render error: " + (err && err.message || err) + "\\n\\n" + (err && err.stack || "");
  document.body.appendChild(banner);
}}

function wireControls() {{
  // Wire UI controls first so they always work even if layout/render
  // later throws. This was a real bug in the previous init order --
  // a thrown exception in fitGraph() left every button disconnected.
  window.addEventListener("resize", () => {{
    try {{ layoutNodes(); renderPositions(); fitGraph(false); }} catch (e) {{ console.error(e); }}
  }});
  document.getElementById("fit-btn").addEventListener("click", () => fitGraph(true));
  document.getElementById("clear-btn").addEventListener("click", clearFocus);
  document.getElementById("zoom-in-btn").addEventListener("click", () => stepZoom(1.25));
  document.getElementById("zoom-out-btn").addEventListener("click", () => stepZoom(0.8));
  svg.addEventListener("click", ev => {{
    if (dragState.moved) {{ dragState.moved = false; return; }}
    if (isBackgroundTarget(ev.target)) clearFocus();
  }});
  // Wheel on svg AND parent stage as a fallback for sandboxed embeds.
  svg.addEventListener("wheel", onWheel, {{ passive: false }});
  document.getElementById("stage").addEventListener("wheel", onWheel, {{ passive: false }});
  // Pointer events first (universal), mouse events as a fallback.
  svg.addEventListener("pointerdown", onSvgPointerDown);
  window.addEventListener("pointermove", onSvgPointerMove);
  window.addEventListener("pointerup", onSvgPointerUp);
  window.addEventListener("pointercancel", onSvgPointerUp);
  svg.addEventListener("mousedown", onSvgMouseDown);
  window.addEventListener("mousemove", onSvgMouseMove);
  window.addEventListener("mouseup", onSvgMouseUp);
}}

function setStatus(text) {{
  const el = document.getElementById("status-indicator");
  if (el) el.textContent = text;
}}

function init() {{
  // Expose key handlers on window so inline onclick attrs work even if
  // addEventListener fails for some reason.
  window.stepZoom = stepZoom;
  window.fitGraph = fitGraph;
  window.clearFocus = clearFocus;
  window.fitToSubject = fitToSubject;
  try {{ wireControls(); }} catch (e) {{ showInitError(e); }}
  try {{ layoutNodes(); }} catch (e) {{ showInitError(e); return; }}
  try {{ renderStatic(); }} catch (e) {{ showInitError(e); return; }}
  try {{ renderSide(); }} catch (e) {{ showInitError(e); return; }}
  try {{ applyFocus(); }} catch (e) {{ showInitError(e); }}
  try {{ fitGraph(false); }} catch (e) {{ showInitError(e); }}
  setStatus(`init OK · scale ${{state.scale.toFixed(2)}}`);
}}

function layoutNodes() {{
  const rect = svg.getBoundingClientRect();
  const width = Math.max(720, rect.width || 1000);
  const height = Math.max(520, rect.height || 720);
  const centerX = width / 2;
  const centerY = height / 2;
  const radiusX = Math.max(180, width * 0.28);
  const radiusY = Math.max(120, height * 0.2);
  const memberships = {{}};
  DATA.ideas.forEach((idea, i) => {{
    const angle = -Math.PI / 2 + (i / Math.max(DATA.ideas.length, 1)) * Math.PI * 2;
    idea.cx = centerX + Math.cos(angle) * radiusX;
    idea.cy = centerY + Math.sin(angle) * radiusY;
    [...idea.claim_ids, ...idea.evidence_ids].forEach(id => {{
      if (!memberships[id]) memberships[id] = [];
      memberships[id].push(idea.id);
    }});
  }});

  for (const node of Object.values(nodeById)) {{
    const ids = memberships[node.id] || [];
    if (ids.length) {{
      node.cx = ids.reduce((sum, id) => sum + ideaById[id].cx, 0) / ids.length;
      node.cy = ids.reduce((sum, id) => sum + ideaById[id].cy, 0) / ids.length;
    }} else {{
      node.cx = centerX;
      node.cy = centerY;
    }}
  }}

  for (const idea of DATA.ideas) {{
    const claimIds = idea.claim_ids.filter(id => nodeById[id]);
    const evidenceIds = idea.evidence_ids.filter(id => nodeById[id]);
    claimIds.forEach((id, idx) => {{
      const spread = (idx - (claimIds.length - 1) / 2) * 62;
      nodeById[id].x = nodeById[id].cx + spread;
      nodeById[id].y = nodeById[id].cy - 58 - Math.abs(spread) * 0.08;
    }});
    evidenceIds.forEach((id, idx) => {{
      const spread = (idx - (evidenceIds.length - 1) / 2) * 66;
      nodeById[id].x = nodeById[id].cx + spread;
      nodeById[id].y = nodeById[id].cy + 58 + Math.abs(spread) * 0.08;
    }});
  }}

  // Belt-and-suspenders: any node that didn't get placed by the
  // subject-membership loop (orphan claim or evidence) gets parked at
  // the canvas center so downstream Math.min / Math.max can't see NaN.
  for (const node of Object.values(nodeById)) {{
    if (!isFinite(node.x) || !isFinite(node.y)) {{
      node.x = centerX;
      node.y = centerY;
      node.cx = centerX;
      node.cy = centerY;
    }}
  }}

  relaxLayout();
}}

function relaxLayout() {{
  const nodes = Object.values(nodeById);
  for (let tick = 0; tick < 120; tick++) {{
    for (const node of nodes) {{
      node.vx = (node.vx || 0) * 0.76 + (node.cx - node.x) * 0.004;
      node.vy = (node.vy || 0) * 0.76 + (node.cy - node.y) * 0.004;
    }}
    for (const edge of DATA.edges) {{
      const a = nodeById[edge.source];
      const b = nodeById[edge.target];
      const dx = b.x - a.x;
      const dy = b.y - a.y;
      const dist = Math.max(1, Math.hypot(dx, dy));
      const desired = 95;
      const force = (dist - desired) * 0.0025;
      const fx = dx / dist * force;
      const fy = dy / dist * force;
      a.vx += fx; a.vy += fy;
      b.vx -= fx; b.vy -= fy;
    }}
    for (let i = 0; i < nodes.length; i++) {{
      for (let j = i + 1; j < nodes.length; j++) {{
        const a = nodes[i];
        const b = nodes[j];
        const dx = b.x - a.x;
        const dy = b.y - a.y;
        const dist = Math.max(1, Math.hypot(dx, dy));
        const min = 34;
        if (dist < min) {{
          const push = (min - dist) * 0.028;
          const fx = dx / dist * push;
          const fy = dy / dist * push;
          a.vx -= fx; a.vy -= fy;
          b.vx += fx; b.vy += fy;
        }}
      }}
    }}
    for (const node of nodes) {{
      node.x += node.vx || 0;
      node.y += node.vy || 0;
    }}
  }}
}}

function renderStatic() {{
  layers.hulls.textContent = "";
  layers.assertionHulls.textContent = "";
  layers.edges.textContent = "";
  layers.nodes.textContent = "";
  layers.labels.textContent = "";
  layers.ideaLabels.textContent = "";
  layers.assertionLabels.textContent = "";

  for (const idea of DATA.ideas) {{
    const path = el("path", {{"class": "idea-hull", fill: idea.color, stroke: idea.color, "data-id": idea.id}});
    path.addEventListener("click", ev => {{ ev.stopPropagation(); focusIdea(idea.id); }});
    path.addEventListener("mousemove", ev => showTip(ev, `<div class="id">${{escapeHtml(idea.id)}}</div><b>${{escapeHtml(idea.label)}}</b>`));
    path.addEventListener("mouseleave", hideTip);
    layers.hulls.appendChild(path);
  }}

  // Inner idea hulls -- one per idea inside the subject, colored by
  // lifecycle status. Only drawn when a subject has 2+ ideas (otherwise
  // there's nothing to distinguish visually).
  for (const subject of DATA.ideas) {{
    const nested = (subject.ideas || []).filter(i => i.member_ids && i.member_ids.length);
    if (nested.length < 2) continue;
    for (const ni of nested) {{
      const status = ni.status || "established";
      const path = el("path", {{
        "class": `assertion-hull ${{status}}`,
        "data-subject": subject.id,
        "data-idea": ni.id,
      }});
      const tipHtml = (
        `<div class="id">${{escapeHtml(ni.id)}} · ${{escapeHtml(status.toUpperCase())}}</div>` +
        `<b>${{escapeHtml(ni.title || "")}}</b><br>` +
        `paper: ${{escapeHtml(ni.paper || "")}}` +
        (ni.contests && ni.contests.length ? `<br>contests ${{ni.contests.length}} idea(s)` : "") +
        (ni.supports && ni.supports.length ? `<br>supported by ${{ni.supports.length}} idea(s)` : "")
      );
      path.addEventListener("mousemove", ev => showTip(ev, tipHtml));
      path.addEventListener("mouseleave", hideTip);
      path.addEventListener("click", ev => {{
        ev.stopPropagation();
        focusInnerIdea(subject.id, ni.id);
      }});
      layers.assertionHulls.appendChild(path);

      const label = el("text", {{
        "class": `assertion-label ${{status}}`,
        "data-subject": subject.id,
        "data-idea": ni.id,
        "text-anchor": "middle",
      }});
      label.textContent = status.toUpperCase() + " · " + (ni.paper || "");
      layers.assertionLabels.appendChild(label);
    }}
  }}

  for (const edge of DATA.edges) {{
    const cls = `edge ${{edgeClass(edge.residual)}}${{edge.semantic ? " semantic" : ""}}`;
    const path = el("path", {{"class": cls, "data-source": edge.source, "data-target": edge.target}});
    path.addEventListener("mousemove", ev => showTip(ev, edgeTip(edge)));
    path.addEventListener("mouseleave", hideTip);
    layers.edges.appendChild(path);
  }}

  for (const node of Object.values(nodeById)) {{
    const group = el("g", {{"class": `node ${{node.kind}}${{node.is_kumar ? " kumar" : ""}}${{node.rewritten ? " rewritten" : ""}}${{node.context_filled ? " context-filled" : ""}}`, "data-id": node.id}});
    const shape = nodeShape(node);
    group.appendChild(shape);
    group.addEventListener("click", ev => {{ ev.stopPropagation(); focusNode(node.id); }});
    group.addEventListener("mousemove", ev => showTip(ev, nodeTip(node)));
    group.addEventListener("mouseleave", hideTip);
    layers.nodes.appendChild(group);

    const label = el("text", {{"class": "label", "data-id": node.id, dy: 24}});
    label.textContent = node.short_id || node.id;
    layers.labels.appendChild(label);
  }}

  for (let i = 0; i < DATA.ideas.length; i++) {{
    const idea = DATA.ideas[i];
    const label = el("text", {{"class": "idea-label", "data-id": idea.id, "text-anchor": "middle"}});
    label.textContent = `Subject ${{i + 1}}`;
    layers.ideaLabels.appendChild(label);
  }}
  renderPositions();
}}

function nodeShape(node) {{
  if (node.kind === "claim" && node.is_kumar) {{
    return el("path", {{"class": "shape", d: STAR_PATH, fill: node.color}});
  }}
  if (node.kind === "evidence" && node.is_kumar) {{
    return el("path", {{"class": "shape", d: DIAMOND_PATH, fill: node.color}});
  }}
  if (node.kind === "claim") {{
    return el("circle", {{"class": "shape", r: 10, fill: node.color}});
  }}
  return el("rect", {{"class": "shape", x: -9, y: -9, width: 18, height: 18, rx: 2, fill: node.color}});
}}

function renderPositions() {{
  for (const path of layers.hulls.querySelectorAll(".idea-hull")) {{
    const idea = ideaById[path.dataset.id];
    path.setAttribute("d", hullPath(idea));
  }}
  for (const path of layers.assertionHulls.querySelectorAll(".assertion-hull")) {{
    const subject = ideaById[path.dataset.subject];
    if (!subject || !subject.ideas) continue;
    const ni = subject.ideas.find(x => x.id === path.dataset.idea);
    if (!ni) continue;
    const nodes = (ni.member_ids || []).map(id => nodeById[id]).filter(Boolean);
    path.setAttribute("d", assertionHullPath(nodes));
  }}
  for (const label of layers.assertionLabels.querySelectorAll(".assertion-label")) {{
    const subject = ideaById[label.dataset.subject];
    if (!subject || !subject.ideas) continue;
    const ni = subject.ideas.find(x => x.id === label.dataset.idea);
    if (!ni) continue;
    const nodes = (ni.member_ids || []).map(id => nodeById[id]).filter(Boolean);
    const center = nodes.length ? {{x: avg(nodes, "x"), y: avg(nodes, "y")}} : {{x: 0, y: 0}};
    label.setAttribute("x", center.x);
    label.setAttribute("y", center.y - 32);
  }}
  for (const path of layers.edges.querySelectorAll(".edge")) {{
    const a = nodeById[path.dataset.source];
    const b = nodeById[path.dataset.target];
    const mx = (a.x + b.x) / 2;
    const my = (a.y + b.y) / 2;
    const dx = b.x - a.x;
    const dy = b.y - a.y;
    const curve = Math.min(26, Math.hypot(dx, dy) * 0.12);
    const nx = -dy / Math.max(1, Math.hypot(dx, dy)) * curve;
    const ny = dx / Math.max(1, Math.hypot(dx, dy)) * curve;
    path.setAttribute("d", `M ${{a.x}} ${{a.y}} Q ${{mx + nx}} ${{my + ny}} ${{b.x}} ${{b.y}}`);
  }}
  for (const group of layers.nodes.querySelectorAll(".node")) {{
    const node = nodeById[group.dataset.id];
    group.setAttribute("transform", `translate(${{node.x}},${{node.y}})`);
  }}
  for (const label of layers.labels.querySelectorAll(".label")) {{
    const node = nodeById[label.dataset.id];
    label.setAttribute("x", node.x);
    label.setAttribute("y", node.y);
  }}
  for (const label of layers.ideaLabels.querySelectorAll(".idea-label")) {{
    const idea = ideaById[label.dataset.id];
    const nodes = [...idea.claim_ids, ...idea.evidence_ids].map(id => nodeById[id]).filter(Boolean);
    const point = ideaLabelPoint(nodes);
    label.setAttribute("x", point.x);
    label.setAttribute("y", point.y);
  }}
}}

function hullPath(idea) {{
  const nodes = [...idea.claim_ids, ...idea.evidence_ids].map(id => nodeById[id]).filter(Boolean);
  if (!nodes.length) return "";
  const points = nodes.map(n => ({{x: n.x, y: n.y}}));
  const pad = 34;
  if (points.length === 1) return circleBlob(points[0], pad + 18);
  const hull = convexHull(points);
  if (hull.length === 1) return circleBlob(hull[0], pad + 18);
  if (hull.length === 2) return pairBlob(hull[0], hull[1], pad + 18);
  return smoothClosedPath(inflateHull(hull, pad));
}}

function assertionHullPath(nodes) {{
  if (!nodes.length) return "";
  const points = nodes.map(n => ({{x: n.x, y: n.y}}));
  const pad = 18;
  if (points.length === 1) return circleBlob(points[0], pad + 12);
  const hull = convexHull(points);
  if (hull.length === 1) return circleBlob(hull[0], pad + 12);
  if (hull.length === 2) return pairBlob(hull[0], hull[1], pad + 12);
  return smoothClosedPath(inflateHull(hull, pad));
}}

function pairBlob(a, b, pad) {{
  // Circle that comfortably contains both endpoints. Much cleaner than
  // the elongated capsule when a hull has only two members.
  const cx = (a.x + b.x) / 2;
  const cy = (a.y + b.y) / 2;
  const r = Math.hypot(b.x - a.x, b.y - a.y) / 2 + pad;
  return circleBlob({{x: cx, y: cy}}, r);
}}

function assertionLabelPoint(nodes, direction) {{
  if (!nodes.length) return {{x: 0, y: 0}};
  const center = {{x: avg(nodes, "x"), y: avg(nodes, "y")}};
  const offset = direction === "positive" ? -34 : 34;
  return {{x: center.x, y: center.y + offset}};
}}


function circleBlob(point, radius) {{
  const c = radius * 0.5522847498;
  return `M ${{point.x}} ${{point.y - radius}} C ${{point.x + c}} ${{point.y - radius}} ${{point.x + radius}} ${{point.y - c}} ${{point.x + radius}} ${{point.y}} C ${{point.x + radius}} ${{point.y + c}} ${{point.x + c}} ${{point.y + radius}} ${{point.x}} ${{point.y + radius}} C ${{point.x - c}} ${{point.y + radius}} ${{point.x - radius}} ${{point.y + c}} ${{point.x - radius}} ${{point.y}} C ${{point.x - radius}} ${{point.y - c}} ${{point.x - c}} ${{point.y - radius}} ${{point.x}} ${{point.y - radius}} Z`;
}}

function capsuleBlob(a, b, radius) {{
  const dx = b.x - a.x;
  const dy = b.y - a.y;
  const length = Math.hypot(dx, dy);
  if (length < 1) return circleBlob(a, radius);
  const nx = -dy / length * radius;
  const ny = dx / length * radius;
  const p1 = {{x: a.x + nx, y: a.y + ny}};
  const p2 = {{x: b.x + nx, y: b.y + ny}};
  const p3 = {{x: b.x - nx, y: b.y - ny}};
  const p4 = {{x: a.x - nx, y: a.y - ny}};
  return `M ${{p1.x}} ${{p1.y}} L ${{p2.x}} ${{p2.y}} A ${{radius}} ${{radius}} 0 0 1 ${{p3.x}} ${{p3.y}} L ${{p4.x}} ${{p4.y}} A ${{radius}} ${{radius}} 0 0 1 ${{p1.x}} ${{p1.y}} Z`;
}}

function convexHull(points) {{
  const unique = [...new Map(points.map(p => [`${{p.x.toFixed(2)}},${{p.y.toFixed(2)}}`, p])).values()];
  if (unique.length <= 2) return unique;
  const sorted = unique.sort((a, b) => a.x - b.x || a.y - b.y);
  const cross = (o, a, b) => (a.x - o.x) * (b.y - o.y) - (a.y - o.y) * (b.x - o.x);
  const lower = [];
  for (const p of sorted) {{
    while (lower.length >= 2 && cross(lower[lower.length - 2], lower[lower.length - 1], p) <= 0) lower.pop();
    lower.push(p);
  }}
  const upper = [];
  for (const p of [...sorted].reverse()) {{
    while (upper.length >= 2 && cross(upper[upper.length - 2], upper[upper.length - 1], p) <= 0) upper.pop();
    upper.push(p);
  }}
  return lower.slice(0, -1).concat(upper.slice(0, -1));
}}

function inflateHull(points, pad) {{
  const cx = avg(points, "x");
  const cy = avg(points, "y");
  return points.map(p => {{
    const dx = p.x - cx;
    const dy = p.y - cy;
    const length = Math.max(1, Math.hypot(dx, dy));
    return {{x: p.x + dx / length * pad, y: p.y + dy / length * pad}};
  }});
}}

function smoothClosedPath(points) {{
  const n = points.length;
  const tension = 0.78;
  let path = `M ${{points[0].x}} ${{points[0].y}}`;
  for (let i = 0; i < n; i++) {{
    const p0 = points[(i - 1 + n) % n];
    const p1 = points[i];
    const p2 = points[(i + 1) % n];
    const p3 = points[(i + 2) % n];
    const c1 = {{x: p1.x + (p2.x - p0.x) * tension / 6, y: p1.y + (p2.y - p0.y) * tension / 6}};
    const c2 = {{x: p2.x - (p3.x - p1.x) * tension / 6, y: p2.y - (p3.y - p1.y) * tension / 6}};
    path += ` C ${{c1.x}} ${{c1.y}} ${{c2.x}} ${{c2.y}} ${{p2.x}} ${{p2.y}}`;
  }}
  return `${{path}} Z`;
}}

function ideaLabelPoint(nodes) {{
  if (!nodes.length) return {{x: 0, y: 0}};
  const center = {{x: avg(nodes, "x"), y: avg(nodes, "y")}};
  if (nodes.length === 1) return {{x: center.x, y: center.y - 28}};
  const top = nodes.reduce((best, node) => node.y < best.y ? node : best, nodes[0]);
  if (center.y - top.y < 24) return {{x: center.x, y: center.y - 20}};
  return {{
    x: center.x * 0.65 + top.x * 0.35,
    y: center.y * 0.65 + top.y * 0.35,
  }};
}}

function avg(nodes, key) {{
  return nodes.reduce((sum, n) => sum + n[key], 0) / Math.max(1, nodes.length);
}}

function renderSide() {{
  const ideaCount = DATA.ideas.reduce((n, s) => n + (s.ideas ? s.ideas.length : 0), 0);
  document.getElementById("meta").innerHTML = `
    <span><b>${{DATA.claims.length}}</b> claims</span>
    <span><b>${{DATA.evidence.length}}</b> evidence</span>
    <span><b>${{DATA.edges.length}}</b> edges</span>
    <span><b>${{DATA.ideas.length}}</b> subjects</span>
    <span><b>${{ideaCount}}</b> ideas</span>
  `;
  document.getElementById("score-grid").innerHTML = `
    <div class="score"><div class="v">${{metric(DATA.metrics.initial_residual)}}</div><div class="k">initial residual</div></div>
    <div class="score"><div class="v">${{metric(DATA.metrics.final_residual)}}</div><div class="k">final residual</div></div>
    <div class="score"><div class="v">${{metric(DATA.metrics.claim_rewrite_distance)}}</div><div class="k">rewrite distance</div></div>
  `;
  document.getElementById("papers").innerHTML = DATA.papers.map(p => `
    <div class="paper-row"><span class="paper-dot" style="background:${{p.color}}"></span><span>${{escapeHtml(p.label)}}</span></div>
  `).join("");
  document.getElementById("ideas").innerHTML = DATA.ideas.map((subject, i) => {{
    const nested = subject.ideas || [];
    const counts = {{ established: 0, contested: 0, novel: 0 }};
    for (const ni of nested) {{
      counts[ni.status] = (counts[ni.status] || 0) + 1;
    }}
    const breakdown = [
      counts.novel ? `<span style="color:var(--accent)"><b>${{counts.novel}}</b> novel</span>` : "",
      counts.contested ? `<span style="color:var(--bad)"><b>${{counts.contested}}</b> contested</span>` : "",
      counts.established ? `<span style="color:var(--ok)"><b>${{counts.established}}</b> established</span>` : "",
    ].filter(Boolean).join(" · ");
    return `
    <div class="legend-card" data-id="${{subject.id}}">
      <div class="legend-row">
        <span class="swatch" style="background:${{subject.color}}"></span>
        <div>
          <div class="legend-title">Subject ${{i + 1}} - ${{escapeHtml(subject.label)}}</div>
          <div class="legend-sub">${{nested.length}} idea${{nested.length === 1 ? "" : "s"}}${{breakdown ? " · " + breakdown : ""}}</div>
        </div>
      </div>
    </div>
  `;}}).join("");
  for (const card of document.querySelectorAll(".legend-card")) {{
    card.addEventListener("click", () => focusIdea(card.dataset.id));
  }}
  // Delegate callout expand-on-click for any callout in the detail panel
  // (which is re-rendered on focus changes, so use event delegation).
  document.getElementById("detail").addEventListener("click", ev => {{
    const callout = ev.target.closest(".callout");
    if (callout) callout.classList.toggle("expanded");
  }});
  renderDefaultDetail();
}}

function renderDefaultDetail() {{
  const high = DATA.edges.filter(e => e.residual >= 0.5).length;
  const mild = DATA.edges.filter(e => e.residual > 0 && e.residual < 0.5).length;
  const zero = DATA.edges.filter(e => e.residual === 0).length;
  document.getElementById("detail").innerHTML = `
    <h3>Reading the graph</h3>
    <p class="muted">Claims are circles, evidence pieces are squares. Outer hulls are <b>subjects</b> (one per comparability group). Edges show where a claim predicts at an evidence piece. Color shows residual after rewriting.</p>
    <div class="callout"><div class="k">Residual edge summary</div>${{zero}} agreement, ${{mild}} mild tension, ${{high}} strong tension.</div>
    <p class="muted">Click a Subject card on the right (or its hull) to expand its <b>ideas</b> with lifecycle status.</p>
  `;
}}

function focusIdea(id) {{
  if (state.focusType === "idea" && state.focusId === id && !state.innerIdeaId) return clearFocus();
  state.focusType = "idea";
  state.focusId = id;
  state.innerIdeaId = null;
  expandSubject(id);
  renderIdeaDetail(ideaById[id]);
  applyFocus();
  fitToSubject(id);
}}

function focusInnerIdea(subjectId, innerIdeaId) {{
  // If subject isn't yet focused (e.g., user clicks a hull from a
  // partially-focused state), bring it up first.
  if (state.focusType !== "idea" || state.focusId !== subjectId) {{
    state.focusType = "idea";
    state.focusId = subjectId;
    expandSubject(subjectId);
  }}
  // Toggle off if clicked twice in a row.
  if (state.innerIdeaId === innerIdeaId) {{
    state.innerIdeaId = null;
    renderIdeaDetail(ideaById[subjectId]);
    applyFocus();
    return;
  }}
  state.innerIdeaId = innerIdeaId;
  renderInnerIdeaDetail(subjectId, innerIdeaId);
  applyFocus();
}}

function focusNode(id) {{
  if (state.focusType === "node" && state.focusId === id) return clearFocus();
  state.focusType = "node";
  state.focusId = id;
  renderNodeDetail(nodeById[id]);
  applyFocus();
}}

function clearFocus() {{
  const wasFocused = !!state.focusType;
  state.focusType = null;
  state.focusId = null;
  state.innerIdeaId = null;
  collapseSubjects();
  renderDefaultDetail();
  applyFocus();
  if (wasFocused) fitGraph(true);
}}

function applyFocus() {{
  const active = activeSet();
  for (const card of document.querySelectorAll(".legend-card")) {{
    card.classList.toggle("active", state.focusType === "idea" && card.dataset.id === state.focusId);
  }}
  for (const path of layers.hulls.querySelectorAll(".idea-hull")) {{
    const activeIdea = state.focusType === "idea" && path.dataset.id === state.focusId;
    const related = state.focusType === "node" && ideaById[path.dataset.id].member_ids.includes(state.focusId);
    path.classList.toggle("focused", activeIdea);
    path.classList.toggle("dimmed", !!state.focusType && !activeIdea && !related);
  }}
  for (const path of layers.assertionHulls.querySelectorAll(".assertion-hull")) {{
    // Inner idea hulls are hidden by default. They expand only when their
    // parent subject is the focused subject -- progressive disclosure.
    const expand = state.focusType === "idea" && path.dataset.subject === state.focusId;
    path.classList.toggle("expanded", expand);
    const isInnerFocus = expand && state.innerIdeaId === path.dataset.idea;
    const isOtherInner = expand && state.innerIdeaId && !isInnerFocus;
    path.classList.toggle("inner-focused", isInnerFocus);
    path.classList.toggle("inner-dimmed", isOtherInner);
  }}
  for (const label of layers.assertionLabels.querySelectorAll(".assertion-label")) {{
    const expand = state.focusType === "idea" && label.dataset.subject === state.focusId;
    label.classList.toggle("expanded", expand);
    const isInnerFocus = expand && state.innerIdeaId === label.dataset.idea;
    const isOtherInner = expand && state.innerIdeaId && !isInnerFocus;
    label.classList.toggle("inner-focused", isInnerFocus);
    label.classList.toggle("inner-dimmed", isOtherInner);
  }}
  for (const label of layers.ideaLabels.querySelectorAll(".idea-label")) {{
    const related = !state.focusType || (state.focusType === "idea" && label.dataset.id === state.focusId) || (state.focusType === "node" && ideaById[label.dataset.id].member_ids.includes(state.focusId));
    label.classList.toggle("dimmed", !related);
  }}
  for (const node of layers.nodes.querySelectorAll(".node")) {{
    const on = !state.focusType || active.has(node.dataset.id);
    node.classList.toggle("dimmed", !on);
    node.classList.toggle("selected", state.focusType === "node" && node.dataset.id === state.focusId);
  }}
  for (const label of layers.labels.querySelectorAll(".label")) {{
    const on = !state.focusType || active.has(label.dataset.id);
    label.classList.toggle("dimmed", !on);
  }}
  for (const edge of layers.edges.querySelectorAll(".edge")) {{
    const on = !state.focusType || (active.has(edge.dataset.source) && active.has(edge.dataset.target));
    edge.classList.toggle("dimmed", !on);
  }}
}}

function activeSet() {{
  if (!state.focusType) return new Set(Object.keys(nodeById));
  if (state.focusType === "idea") {{
    if (state.innerIdeaId) {{
      const subject = ideaById[state.focusId];
      const inner = ((subject && subject.ideas) || []).find(i => i.id === state.innerIdeaId);
      if (inner && inner.member_ids) return new Set(inner.member_ids);
    }}
    return new Set(ideaById[state.focusId].member_ids);
  }}
  const set = new Set([state.focusId]);
  for (const edge of edgesByNode[state.focusId] || []) {{
    set.add(edge.source === state.focusId ? edge.target : edge.source);
  }}
  return set;
}}

function renderInnerIdeaDetail(subjectId, innerIdeaId) {{
  const subject = ideaById[subjectId];
  if (!subject) return;
  const ni = (subject.ideas || []).find(i => i.id === innerIdeaId);
  if (!ni) return;
  const status = ni.status || "established";
  const statusClass = status === "contested" ? "high" : status === "novel" ? "blocking" : "exploratory";
  const memberPills = (ni.member_ids || []).map(id => pill(nodeById[id])).join("");
  document.getElementById("detail").innerHTML = `
    <h3>${{escapeHtml(subject.label)}}</h3>
    <p class="muted">Idea inside this subject:</p>
    <div class="callout">
      <div class="k"><span class="priority ${{statusClass}}">${{status.toUpperCase()}}</span>${{escapeHtml(ni.paper || "")}}</div>
      <div>${{escapeHtml(ni.title || ni.id)}}</div>
    </div>
    <h2>Claims and evidence in this idea</h2>
    <div class="pill-row">${{memberPills}}</div>
    ${{(ni.contests || []).length ? `<h2>Contests</h2><div class="pill-row">${{(ni.contests || []).map(cid => {{ const t = ideaById[subjectId] && (ideaById[subjectId].ideas || []).find(x => x.id === cid); return t ? `<span class="pill" style="background:var(--bad)">${{escapeHtml(t.paper || cid)}}</span>` : ""; }}).join("")}}</div>` : ""}}
    ${{(ni.supports || []).length ? `<h2>Supported by</h2><div class="pill-row">${{(ni.supports || []).map(sid => {{ const t = ideaById[subjectId] && (ideaById[subjectId].ideas || []).find(x => x.id === sid); return t ? `<span class="pill" style="background:var(--ok)">${{escapeHtml(t.paper || sid)}}</span>` : ""; }}).join("")}}</div>` : ""}}
    <p class="muted" style="margin-top:14px;">Click the same idea hull again or click elsewhere in the subject to return to the subject view.</p>
  `;
  wirePills();
}}

function renderIdeaDetail(subject) {{
  const nested = subject.ideas || [];
  const statusBlock = ni => {{
    const cls = ni.status || "established";
    const contests = (ni.contests || []).length;
    const supports = (ni.supports || []).length;
    return `
      <div class="callout ${{cls === "contested" ? "bad" : cls === "novel" ? "" : ""}}">
        <div class="k"><span class="priority ${{cls === "contested" ? "high" : cls === "novel" ? "blocking" : "exploratory"}}">${{cls.toUpperCase()}}</span>${{escapeHtml(ni.paper || "")}}</div>
        <div>${{escapeHtml(ni.title || ni.id)}}</div>
        <div class="muted" style="margin-top:4px;font-size:11px;">
          ${{ni.claim_ids ? ni.claim_ids.length : 0}} claim(s) ·
          ${{ni.evidence_ids ? ni.evidence_ids.length : 0}} evidence ·
          ${{contests}} contests · ${{supports}} supports
        </div>
      </div>
    `;
  }};
  document.getElementById("detail").innerHTML = `
    <h3>${{escapeHtml(subject.label)}}</h3>
    <p class="muted">${{escapeHtml(subject.scope.system || "")}}<br>${{escapeHtml(subject.scope.framework || "")}}</p>
    <h2>Ideas in this subject</h2>
    ${{nested.length ? nested.map(statusBlock).join("") : "<p class='muted'>No ideas yet (ungrouped subject).</p>"}}
    <h2>All claims</h2>
    <div class="pill-row">${{subject.claim_ids.map(id => pill(nodeById[id])).join("")}}</div>
    <h2>All evidence</h2>
    <div class="pill-row">${{subject.evidence_ids.map(id => pill(nodeById[id])).join("")}}</div>
    ${{subject.open_questions.map(questionBlock).join("")}}
  `;
  wirePills();
}}

function questionBlock(q) {{
  const priority = q.priority || "medium";
  return `
    <div class="callout question ${{priorityClass(priority)}}">
      <div class="k"><span class="priority ${{priorityClass(priority)}}">${{escapeHtml(priorityLabel(priority))}}</span>Open question</div>
      ${{escapeHtml(q.question)}}
      <div class="next-work">
        ${{(q.suggested_next_steps || []).map(nextStepBlock).join("")}}
      </div>
    </div>
  `;
}}

function priorityClass(value) {{
  const normalized = String(value || "medium").toLowerCase().replace(/[^a-z0-9_-]/g, "-");
  return ["blocking", "high", "medium", "exploratory"].includes(normalized) ? normalized : "medium";
}}

function priorityLabel(value) {{
  const normalized = priorityClass(value);
  return normalized === "blocking" ? "blocking" : normalized;
}}

function nextStepBlock(step) {{
  if (typeof step === "string") {{
    return `<div class="next-step"><span class="kind">next</span><span class="title">${{escapeHtml(step)}}</span></div>`;
  }}
  return `
    <div class="next-step">
      <span class="kind">${{escapeHtml(step.kind || "next")}}</span>
      <span class="title">${{escapeHtml(step.title || "Suggested work")}}</span>
      ${{step.description ? `<div class="desc">${{escapeHtml(step.description)}}</div>` : ""}}
    </div>
  `;
}}

function renderNodeDetail(node) {{
  const edges = edgesByNode[node.id] || [];
  document.getElementById("detail").innerHTML = `
    <h3><span class="mono">${{escapeHtml(node.id)}}</span></h3>
    <p>${{escapeHtml(node.label)}}</p>
    <p class="muted">${{escapeHtml(node.paper_label)}}</p>
    ${{node.kind === "claim" ? claimState(node) : evidenceState(node)}}
    <h2>Connected edges</h2>
    ${{edges.map(edge => {{
      const other = edge.source === node.id ? edge.target : edge.source;
      return `<div class="callout ${{edge.residual >= 0.5 ? "bad" : edge.residual > 0 ? "warn" : ""}}"><div class="k">${{escapeHtml(edge.edge_id)}}</div><span class="mono">${{escapeHtml(other)}}</span><br>residual=${{metric(edge.residual)}}; predicted=${{metric(edge.predicted)}}; actual=${{metric(edge.actual)}}</div>`;
    }}).join("")}}
  `;
}}

function claimState(node) {{
  return `${{hygieneBlock(node)}}${{rewriteBlock(node)}}${{claimList("Strengths", node.strengths, "No strengths recorded.")}}${{claimList("Weaknesses", node.weaknesses, "No weaknesses recorded.")}}`;
}}

function hygieneBlock(node) {{
  const h = node.hygiene || {{}};
  const status = h.status || "not_applicable";
  if (status === "not_applicable" && !node.stature) return "";
  let body = "";
  if (status === "implicit_headline") {{
    const targets = (h.contradicting_targets || []).map(t => `<span class="mono">${{escapeHtml(t)}}</span>`).join(", ");
    body = `<div class="callout bad"><div class="k">Implicit headline</div>This claim's home stance propagated to comparable evidence in other papers and CONTRADICTS them at: ${{targets || "(none)"}}. Structural suspect.</div>`;
  }} else if (status === "consensus_aligned") {{
    const targets = (h.propagated_targets || []).map(t => `<span class="mono">${{escapeHtml(t)}}</span>`).join(", ");
    body = `<div class="callout"><div class="k">Consensus-aligned</div>Propagated to comparable evidence in other papers and agreed at full strength: ${{targets || "(none)"}}.</div>`;
  }} else if (status === "scoped_explicit") {{
    body = `<div class="callout"><div class="k">Scope-aware</div>Explicitly addresses every member of its comparability group(s).</div>`;
  }}
  if (node.stature !== undefined) {{
    body += `<div class="callout"><div class="k">Stature</div>Backed by <b>${{node.stature}}</b> independent paper(s) at full strength.</div>`;
  }}
  return body;
}}

function rewriteBlock(node) {{
  if (!node.rewritten) return "";
  return `
    <div class="callout">
      <div class="k">Original claim</div>
      ${{escapeHtml(node.original_label || node.label)}}
    </div>
    <div class="callout">
      <div class="k">Edited claim</div>
      ${{escapeHtml(node.edited_label || node.label)}}
    </div>
  `;
}}

function claimList(title, items, fallback) {{
  const values = Array.isArray(items) && items.length ? items : [fallback];
  return `<h2>${{escapeHtml(title)}}</h2><ul>${{values.map(item => `<li>${{escapeHtml(item)}}</li>`).join("")}}</ul>`;
}}

function evidenceState(node) {{
  return `<div class="callout"><div class="k">Evidence core</div>${{escapeHtml(node.observable)}} = <span class="mono">${{metric(node.core)}}</span><br><span class="muted">${{escapeHtml(node.context)}}</span></div>`;
}}

function pill(node) {{
  if (!node) return "";
  return `<span class="pill" data-node="${{node.id}}" title="${{escapeHtml(node.id)}}" style="background:${{node.color}}">${{escapeHtml(node.short_id || node.id)}}</span>`;
}}

function wirePills() {{
  for (const item of document.querySelectorAll(".pill[data-node]")) {{
    item.addEventListener("click", () => focusNode(item.dataset.node));
  }}
}}

function edgeClass(residual) {{
  if (residual >= 0.5) return "high";
  if (residual >= 0.05) return "mild";
  if (residual > 0) return "tiny";
  return "zero";
}}

function nodeTip(node) {{
  return `<div class="id">${{escapeHtml(node.id)}}</div><b>${{escapeHtml(node.label)}}</b><br><span>${{escapeHtml(node.paper_label)}}</span>`;
}}

function edgeTip(edge) {{
  return `<div class="id">${{escapeHtml(edge.edge_id)}}</div><b>${{escapeHtml(edge.source)}} -> ${{escapeHtml(edge.target)}}</b><br>residual=${{metric(edge.residual)}}; predicted=${{metric(edge.predicted)}}; actual=${{metric(edge.actual)}}`;
}}

function showTip(ev, content) {{
  tooltip.innerHTML = content;
  tooltip.style.opacity = "1";
  const rect = document.getElementById("stage").getBoundingClientRect();
  tooltip.style.left = Math.min(rect.width - 320, ev.clientX - rect.left + 14) + "px";
  tooltip.style.top = Math.max(8, ev.clientY - rect.top + 14) + "px";
}}

function hideTip() {{
  tooltip.style.opacity = "0";
}}

function fitGraph(animate = true) {{
  const nodes = Object.values(nodeById);
  if (!nodes.length) return;
  const minX = Math.min(...nodes.map(n => n.x)) - 90;
  const maxX = Math.max(...nodes.map(n => n.x)) + 90;
  const minY = Math.min(...nodes.map(n => n.y)) - 90;
  const maxY = Math.max(...nodes.map(n => n.y)) + 90;
  fitToBox(minX, maxX, minY, maxY, {{ animate, maxScale: 1.4 }});
}}

function fitToSubject(subjectId, animate = true) {{
  const subject = ideaById[subjectId];
  if (!subject || !subject.member_ids) return;
  const nodes = subject.member_ids.map(id => nodeById[id]).filter(Boolean);
  if (!nodes.length) return;
  const pad = 70;
  const minX = Math.min(...nodes.map(n => n.x)) - pad;
  const maxX = Math.max(...nodes.map(n => n.x)) + pad;
  const minY = Math.min(...nodes.map(n => n.y)) - pad;
  const maxY = Math.max(...nodes.map(n => n.y)) + pad;
  fitToBox(minX, maxX, minY, maxY, {{ animate, maxScale: 3.0 }});
}}

// --- expand-on-focus ---
// When a subject is focused, scale its members outward from the subject
// center so they spread apart. Save originals so clearFocus can collapse
// them back to the tight global layout.
const SPREAD_FACTOR = 2.6;
const savedPositions = {{}};

function expandSubject(subjectId) {{
  // Always collapse any previously expanded subject before expanding a new one.
  collapseSubjects();
  const subject = ideaById[subjectId];
  if (!subject || !subject.member_ids) return;
  const members = subject.member_ids.map(id => nodeById[id]).filter(Boolean);
  if (members.length < 2) return;
  const cx = members.reduce((s, n) => s + n.x, 0) / members.length;
  const cy = members.reduce((s, n) => s + n.y, 0) / members.length;
  for (const node of members) {{
    savedPositions[node.id] = {{ x: node.x, y: node.y }};
    node.x = cx + (node.x - cx) * SPREAD_FACTOR;
    node.y = cy + (node.y - cy) * SPREAD_FACTOR;
  }}
  renderPositions();
}}

function collapseSubjects() {{
  let touched = false;
  for (const [id, pos] of Object.entries(savedPositions)) {{
    const node = nodeById[id];
    if (node) {{ node.x = pos.x; node.y = pos.y; touched = true; }}
    delete savedPositions[id];
  }}
  if (touched) renderPositions();
}}

function fitToBox(minX, maxX, minY, maxY, opts = {{}}) {{
  const animate = opts.animate !== false;
  const maxScale = opts.maxScale || 3.0;
  const rect = svg.getBoundingClientRect();
  const dx = Math.max(50, maxX - minX);
  const dy = Math.max(50, maxY - minY);
  const targetScale = Math.min(rect.width / dx, rect.height / dy, maxScale);
  const targetTx = (rect.width - (minX + maxX) * targetScale) / 2;
  const targetTy = (rect.height - (minY + maxY) * targetScale) / 2;
  if (animate) {{
    animateTransform(targetScale, targetTx, targetTy);
  }} else {{
    state.scale = targetScale;
    state.tx = targetTx;
    state.ty = targetTy;
    applyTransform();
  }}
}}

let animationFrame = null;
function animateTransform(scale, tx, ty, duration = 360) {{
  if (animationFrame) cancelAnimationFrame(animationFrame);
  const s0 = state.scale, x0 = state.tx, y0 = state.ty;
  const t0 = performance.now();
  const ease = t => 1 - Math.pow(1 - t, 3);
  function step(now) {{
    const u = Math.min(1, (now - t0) / duration);
    const e = ease(u);
    state.scale = s0 + (scale - s0) * e;
    state.tx = x0 + (tx - x0) * e;
    state.ty = y0 + (ty - y0) * e;
    applyTransform();
    if (u < 1) animationFrame = requestAnimationFrame(step);
    else animationFrame = null;
  }}
  animationFrame = requestAnimationFrame(step);
}}

function applyTransform() {{
  layers.root.setAttribute("transform", `translate(${{state.tx}},${{state.ty}}) scale(${{state.scale}})`);
  const el = document.getElementById("status-indicator");
  if (el) el.textContent = `scale ${{state.scale.toFixed(2)}}` + (state.focusType === "idea" ? ` · subject ${{state.focusId}}` : "");
}}

function stepZoom(factor) {{
  if (animationFrame) {{ cancelAnimationFrame(animationFrame); animationFrame = null; }}
  const next = Math.max(0.4, Math.min(5.0, state.scale * factor));
  const rect = svg.getBoundingClientRect();
  const cx = rect.width / 2;
  const cy = rect.height / 2;
  state.tx = cx - (cx - state.tx) * (next / state.scale);
  state.ty = cy - (cy - state.ty) * (next / state.scale);
  state.scale = next;
  applyTransform();
}}

function onWheel(ev) {{
  ev.preventDefault();
  if (animationFrame) {{ cancelAnimationFrame(animationFrame); animationFrame = null; }}
  const factor = ev.deltaY < 0 ? 1.08 : 0.92;
  const next = Math.max(0.4, Math.min(5.0, state.scale * factor));
  const rect = svg.getBoundingClientRect();
  const mx = ev.clientX - rect.left;
  const my = ev.clientY - rect.top;
  state.tx = mx - (mx - state.tx) * (next / state.scale);
  state.ty = my - (my - state.ty) * (next / state.scale);
  state.scale = next;
  applyTransform();
}}

// --- drag-to-pan ---
const dragState = {{ active: false, startX: 0, startY: 0, baseTx: 0, baseTy: 0, moved: false }};

function isBackgroundTarget(el) {{
  // pan when clicking on raw svg, the root <g>, or the hulls layer
  // (never start a pan on a node, label, edge, or interactive hull).
  if (!el) return false;
  if (el === svg) return true;
  const tag = el.tagName;
  if (tag === "g") return true;
  if (el.classList && el.classList.contains("idea-hull")) return false;  // hulls click-focus
  return false;
}}

function onSvgMouseDown(ev) {{
  if (ev.button !== 0) return;
  if (!isBackgroundTarget(ev.target)) return;
  if (animationFrame) {{ cancelAnimationFrame(animationFrame); animationFrame = null; }}
  dragState.active = true;
  dragState.moved = false;
  dragState.startX = ev.clientX;
  dragState.startY = ev.clientY;
  dragState.baseTx = state.tx;
  dragState.baseTy = state.ty;
  svg.style.cursor = "grabbing";
}}

function onSvgMouseMove(ev) {{
  if (!dragState.active) return;
  const dx = ev.clientX - dragState.startX;
  const dy = ev.clientY - dragState.startY;
  if (Math.abs(dx) + Math.abs(dy) > 3) dragState.moved = true;
  state.tx = dragState.baseTx + dx;
  state.ty = dragState.baseTy + dy;
  applyTransform();
}}

function onSvgMouseUp() {{
  if (!dragState.active) return;
  dragState.active = false;
  svg.style.cursor = "";
}}

// Pointer-event versions (cover trackpad / pen / mobile).
function onSvgPointerDown(ev) {{
  if (ev.pointerType === "mouse" && ev.button !== 0) return;
  if (!isBackgroundTarget(ev.target)) return;
  if (animationFrame) {{ cancelAnimationFrame(animationFrame); animationFrame = null; }}
  try {{ svg.setPointerCapture && svg.setPointerCapture(ev.pointerId); }} catch (_) {{}}
  dragState.active = true;
  dragState.moved = false;
  dragState.startX = ev.clientX;
  dragState.startY = ev.clientY;
  dragState.baseTx = state.tx;
  dragState.baseTy = state.ty;
  svg.style.cursor = "grabbing";
}}

function onSvgPointerMove(ev) {{
  if (!dragState.active) return;
  const dx = ev.clientX - dragState.startX;
  const dy = ev.clientY - dragState.startY;
  if (Math.abs(dx) + Math.abs(dy) > 3) dragState.moved = true;
  state.tx = dragState.baseTx + dx;
  state.ty = dragState.baseTy + dy;
  applyTransform();
}}

function onSvgPointerUp() {{
  if (!dragState.active) return;
  dragState.active = false;
  svg.style.cursor = "";
}}

init();
  </script>
</body>
</html>
"""
    run_dir.joinpath("constellation.html").write_text(doc)


def _viz_data(
    papers: list[Json],
    claims: list[Json],
    evidence: list[Json],
    sheaf: Json,
    ideas: list[Json],
) -> Json:
    palette = [
        "#2563eb",
        "#dc2626",
        "#16a34a",
        "#d97706",
        "#7c3aed",
        "#0891b2",
        "#be185d",
        "#475569",
        "#0d9488",
        "#9333ea",
        "#ca8a04",
        "#e11d48",
        "#0284c7",
        "#65a30d",
    ]
    paper_labels = {
        paper["paper_id"]: _paper_label(paper) for paper in papers
    }
    # Assign paper colors deterministically by sorted paper_id so the
    # same paper gets the same color across runs (prior vs situate).
    # Kumar papers always use gold and don't consume a palette slot.
    paper_colors: Json = {}
    non_kumar_sorted = sorted(
        (p for p in papers if not _is_kumar_paper(p["paper_id"], paper_labels.get(p["paper_id"], ""))),
        key=lambda p: p["paper_id"],
    )
    for i, paper in enumerate(non_kumar_sorted):
        paper_colors[paper["paper_id"]] = palette[i % len(palette)]
    for paper in papers:
        if _is_kumar_paper(paper["paper_id"], paper_labels.get(paper["paper_id"], "")):
            paper_colors[paper["paper_id"]] = "#eab308"
    claim_by_id = {claim["claim_id"]: claim for claim in claims}
    evidence_by_id = {ev["evidence_id"]: ev for ev in evidence}
    final_residual_by_edge = {
        item["edge_id"]: item for item in sheaf["residuals"]["final"]
    }

    stature_map = sheaf.get("stature") or {}
    hygiene_map = sheaf.get("claim_hygiene") or {}
    semantic_edge_ids = set(sheaf.get("semantic_edge_ids") or [])

    claim_nodes = []
    for claim in claims:
        paper_id = claim["paper_id"]
        cid = claim["claim_id"]
        claim_nodes.append(
            {
                "id": cid,
                "short_id": cid,
                "kind": "claim",
                "label": claim["label"],
                "original_label": claim["label"],
                "edited_label": _edited_claim_label(claim),
                "paper": paper_id,
                "paper_label": paper_labels.get(paper_id, paper_id),
                "color": paper_colors.get(paper_id, "#64748b"),
                "is_kumar": _is_kumar_paper(paper_id, paper_labels.get(paper_id, "")),
                "x_in": claim["x_final"][0],
                "x_out": claim["x_final"][1],
                "x_init": claim.get("x_init", []),
                "x_final": claim.get("x_final", []),
                "rewritten": bool(claim.get("rewrite_history")),
                "rewrite_history": claim.get("rewrite_history", []),
                "strengths": claim.get("strengths", _claim_strengths(claim)),
                "weaknesses": claim.get("weaknesses", []),
                "stature": stature_map.get(cid, 0),
                "hygiene": hygiene_map.get(cid, {"status": "not_applicable"}),
            }
        )

    evidence_nodes = []
    for i, ev in enumerate(evidence, start=1):
        paper_id = ev["paper_id"]
        first_dim = ev["core"]["dimensions"][0]
        context = ev.get("context", {})
        evidence_nodes.append(
            {
                "id": ev["evidence_id"],
                "short_id": f"E_{i:02d}",
                "kind": "evidence",
                "label": ev["label"],
                "paper": paper_id,
                "paper_label": paper_labels.get(paper_id, paper_id),
                "color": paper_colors.get(paper_id, "#64748b"),
                "is_kumar": _is_kumar_paper(paper_id, paper_labels.get(paper_id, "")),
                "core": first_dim["value"],
                "observable": first_dim["name"],
                "context": "; ".join(
                    part
                    for part in [
                        context.get("system", ""),
                        context.get("framework", ""),
                        context.get("regime", ""),
                    ]
                    if part
                ),
                "context_filled": bool(context.get("filled_by_pipeline")),
            }
        )

    edges = []
    for edge in sheaf["edges"]:
        residual = final_residual_by_edge[edge["edge_id"]]
        dim = residual["dimensions"][0]
        edges.append(
            {
                "edge_id": edge["edge_id"],
                "source": edge["claim_id"],
                "target": edge["evidence_id"],
                "in_regime": edge["regime_tag"] == "in_regime",
                "base_pred": dim["base_prediction"],
                "actual": dim["actual"],
                "predicted": dim["predicted"],
                "strength": dim["strength"],
                "residual": residual["residual_sq"],
                "observable": dim["name"],
                "semantic": edge["edge_id"] in semantic_edge_ids,
            }
        )

    idea_palette = ["#2563eb", "#0891b2", "#16a34a", "#d97706", "#7c3aed", "#be185d", "#475569"]
    # Stable color per subject: sort by group_id (which is the same
    # comparability key in both corpora) so the same subject gets the
    # same color across runs. Ungrouped always lands at the tail.
    def _idea_sort_key(idea: Json) -> tuple[int, str]:
        gid = idea.get("group_id", idea["idea_id"])
        return (1 if gid == "ungrouped" else 0, gid)
    sorted_ideas = sorted(ideas, key=_idea_sort_key)
    idea_color_by_id = {
        idea["idea_id"]: idea_palette[i % len(idea_palette)]
        for i, idea in enumerate(sorted_ideas)
    }
    idea_nodes = []
    for idea in ideas:
        member_ids = [*idea["contributing_claims"], *idea["contributing_evidence"]]
        # Build per-(nested) idea data for the inner hull renderer. Each
        # subject can contain many ideas with lifecycle status; we render
        # one dashed inner hull per idea colored by its status (green =
        # established, red = contested, blue = novel).
        nested: list[Json] = []
        for nested_idea in idea.get("ideas", []) or []:
            nested.append({
                "id": nested_idea["idea_id"],
                "title": nested_idea.get("title", ""),
                "status": nested_idea.get("status", "established"),
                "paper": (nested_idea.get("contributing_papers") or [""])[0],
                "claim_ids": nested_idea.get("contributing_claims", []),
                "evidence_ids": sorted(set((nested_idea.get("stance") or {}).keys())),
                "member_ids": [
                    *nested_idea.get("contributing_claims", []),
                    *sorted(set((nested_idea.get("stance") or {}).keys())),
                ],
                "contests": [c["idea_id"] for c in (nested_idea.get("contests") or [])],
                "supports": [s["idea_id"] for s in (nested_idea.get("supports") or [])],
            })
        idea_nodes.append(
            {
                "id": idea["idea_id"],
                "label": idea["title"],
                "color": idea_color_by_id[idea["idea_id"]],
                "claim_ids": idea["contributing_claims"],
                "evidence_ids": idea["contributing_evidence"],
                "member_ids": member_ids,
                "scope": idea.get("scope", {}),
                "remaining_tensions": idea.get("remaining_tensions", []),
                "tensions_resolved": idea.get("tensions_resolved", []),
                "open_questions": idea.get("open_questions", []),
                "ideas": nested,
                "tensions": idea.get("tensions") or [],
            }
        )

    return {
        "claims": claim_nodes,
        "evidence": evidence_nodes,
        "edges": edges,
        "ideas": idea_nodes,
        "papers": [
            {
                "id": paper["paper_id"],
                "label": paper_labels.get(paper["paper_id"], paper["paper_id"]),
                "color": paper_colors.get(paper["paper_id"], "#64748b"),
            }
            for paper in papers
        ],
        "metrics": {
            "initial_residual": sheaf["objective"]["initial_residual"],
            "final_residual": sheaf["objective"]["final_residual"],
            "claim_rewrite_distance": sheaf["objective"]["claim_rewrite_distance"],
        },
    }


def _paper_label(paper: Json) -> str:
    year = f" ({paper['year']})" if paper.get("year") else ""
    return f"{paper.get('title', paper['paper_id'])}{year}"


def _report_title(sheaf: Json) -> str:
    sheaf_id = str(sheaf.get("sheaf_id", "constellation"))
    corpus = sheaf_id.removesuffix("_v05").replace("_", " ").strip()
    corpus_name = corpus.title() if corpus else "Constellation"
    return f"{corpus_name} v0.5 - Ideas Constellation"


def _step_kind(step: Json | str) -> str:
    if isinstance(step, str):
        return "step"
    return str(step.get("kind", "step"))


def _step_title(step: Json | str) -> str:
    if isinstance(step, str):
        return step
    title = str(step.get("title", "Suggested work"))
    description = str(step.get("description", "")).strip()
    return f"{title} - {description}" if description else title


def _claim_strengths(claim: Json) -> list[str]:
    predictions = claim.get("predictions", [])
    if predictions:
        return [f"Makes {len(predictions)} explicit prediction(s) against evidence nodes."]
    return ["Provides a scoped literature claim for review."]


def _edited_claim_label(claim: Json) -> str:
    history = claim.get("rewrite_history", [])
    if not history:
        return claim["label"]
    final_state = claim.get("x_final", [1.0, 1.0])
    home = claim.get("home_regime", {})
    framework = home.get("framework") or "its home framework"
    system = home.get("system") or "its home regime"
    out_strength = float(final_state[1]) if len(final_state) > 1 else 1.0
    return (
        f"{claim['label']} Scoped reading: keep full strength for {system} under "
        f"{framework}, but treat out-of-regime projections at strength {out_strength:.1f}."
    )


def _is_kumar_paper(paper_id: str, label: str) -> bool:
    normalized = f"{paper_id} {label}".lower()
    return "kumar" in normalized or paper_id == "atlas2026"
