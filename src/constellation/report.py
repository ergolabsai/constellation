from __future__ import annotations

import html
import json
from pathlib import Path

from .util import Json


def write_report(run_dir: Path, papers: list[Json], claims: list[Json], evidence: list[Json], sheaf: Json, ideas: list[Json]) -> None:
    lines = [
        "# Constellation Report",
        "",
        f"- Papers: {len(papers)}",
        f"- Claims: {len(claims)}",
        f"- Evidence pieces: {len(evidence)}",
        f"- Claim-evidence edges: {len(sheaf['edges'])}",
        f"- Initial residual: {sheaf['objective']['initial_residual']:.3f}",
        f"- Final residual: {sheaf['objective']['final_residual']:.3f}",
        f"- Claim rewrite distance: {sheaf['objective']['claim_rewrite_distance']:.3f}",
        "",
        "## Rewrites",
        "",
    ]
    if sheaf["operations"]:
        for op in sheaf["operations"]:
            lines.append(
                f"- `{op['claim_id']}`: `{op['from']}` -> `{op['to']}`; "
                f"residual {op['initial_residual']:.3f} -> {op['final_residual']:.3f}"
            )
    else:
        lines.append("- No claim rewrites were accepted.")

    lines.extend(["", "## Ideas", ""])
    for idea in ideas:
        lines.append(f"### {idea['title']}")
        lines.append("")
        lines.append(f"- Claims: {', '.join(f'`{c}`' for c in idea['contributing_claims'])}")
        lines.append(f"- Evidence: {', '.join(f'`{e}`' for e in idea['contributing_evidence'])}")
        if idea["tensions_resolved"]:
            lines.append(f"- Resolved tensions: {len(idea['tensions_resolved'])}")
        if idea["remaining_tensions"]:
            lines.append(f"- Remaining tensions: {len(idea['remaining_tensions'])}")
        for question in idea["open_questions"]:
            lines.append(f"- Open question ({question['priority']}): {question['question']}")
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
    doc = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Constellation - Ideas</title>
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
    #graph-svg {{ width: 100%; height: 100%; display: block; background: var(--bg); }}
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
      display: flex;
      gap: 6px;
      padding: 6px;
      border: 1px solid var(--border);
      border-radius: 8px;
      background: rgba(255, 255, 255, 0.88);
      box-shadow: var(--shadow);
      backdrop-filter: blur(8px);
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
    .edge.dimmed, .node.dimmed, .label.dimmed, .idea-hull.dimmed, .idea-label.dimmed {{ opacity: 0.12; }}
    .idea-hull {{
      fill-opacity: 0.14;
      stroke-opacity: 0.72;
      stroke-width: 1.4;
      cursor: pointer;
      transition: opacity 160ms, fill-opacity 160ms, stroke-width 160ms;
    }}
    .idea-hull.focused {{ fill-opacity: 0.24; stroke-width: 3; }}
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
    }}
    .legend-card:hover {{ background: #f8fafc; transform: translateY(-1px); }}
    .legend-card.active {{ border-color: var(--accent); box-shadow: inset 3px 0 0 var(--accent); }}
    .legend-row {{ display: flex; gap: 8px; align-items: flex-start; }}
    .swatch {{ flex: 0 0 14px; width: 14px; height: 14px; border-radius: 4px; margin-top: 2px; }}
    .legend-title {{ font-weight: 700; font-size: 12px; line-height: 1.25; }}
    .legend-sub {{ color: var(--muted); font-size: 11px; margin-top: 2px; }}
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
    }}
    .callout.warn {{ border-left-color: var(--warn); background: #fff7ed; }}
    .callout.bad {{ border-left-color: var(--bad); background: #fef2f2; }}
    .callout .k {{ color: var(--muted); font-size: 11px; font-weight: 700; }}
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
      <h1>Shumlak v0.5 - Ideas Constellation</h1>
      <div class="muted">Bipartite claim/evidence sheaf with residual-aware rewrites</div>
    </div>
    <div class="meta" id="meta"></div>
  </header>
  <main>
    <section id="stage">
      <svg id="graph-svg" role="img" aria-label="Claim and evidence constellation"></svg>
      <div class="toolbar">
        <button id="fit-btn" type="button" title="Fit graph">Fit</button>
        <button id="clear-btn" type="button" title="Clear focus">Clear</button>
      </div>
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
          <svg width="22" height="22" viewBox="-12 -12 24 24"><rect x="-9" y="-9" width="18" height="18" rx="2" fill="#64748b" stroke="white" stroke-width="2"/></svg>
          <span><b>evidence</b> square, dashed when context-filled</span>
        </div>
      </div>
      <h2>Edges</h2>
      <div class="edge-legend">
        <div class="edge-line"><svg width="42" height="12"><line x1="2" y1="6" x2="40" y2="6" stroke="#cbd5e1" stroke-width="2"/></svg><span><b>agreement</b> residual near 0</span></div>
        <div class="edge-line"><svg width="42" height="12"><line x1="2" y1="6" x2="40" y2="6" stroke="#d97706" stroke-width="3"/></svg><span><b>mild tension</b> residual below 0.5</span></div>
        <div class="edge-line"><svg width="42" height="12"><line x1="2" y1="6" x2="40" y2="6" stroke="#dc2626" stroke-width="4"/></svg><span><b>strong tension</b> residual 0.5 or above</span></div>
      </div>
      <div class="score-grid" id="score-grid"></div>
      <h2>Papers</h2>
      <div id="papers"></div>
      <h2>Ideas</h2>
      <div id="ideas"></div>
      <div id="detail" class="detail"></div>
    </aside>
  </main>
  <script>
const DATA = {data_json};

const SVG_NS = "http://www.w3.org/2000/svg";
const svg = document.getElementById("graph-svg");
const tooltip = document.getElementById("tooltip");
const state = {{ focusType: null, focusId: null, scale: 1, tx: 0, ty: 0 }};
const nodeById = Object.fromEntries([...DATA.claims, ...DATA.evidence].map(n => [n.id, n]));
const ideaById = Object.fromEntries(DATA.ideas.map(i => [i.id, i]));
const edgesByNode = Object.fromEntries(Object.keys(nodeById).map(id => [id, []]));
for (const edge of DATA.edges) {{
  edgesByNode[edge.source].push(edge);
  edgesByNode[edge.target].push(edge);
}}

const layers = {{
  root: el("g"),
  hulls: el("g"),
  edges: el("g"),
  nodes: el("g"),
  labels: el("g"),
  ideaLabels: el("g"),
}};
svg.appendChild(layers.root);
layers.root.append(layers.hulls, layers.edges, layers.nodes, layers.labels, layers.ideaLabels);

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

function init() {{
  layoutNodes();
  renderStatic();
  renderSide();
  applyFocus();
  fitGraph();
  window.addEventListener("resize", () => {{ layoutNodes(); renderPositions(); fitGraph(); }});
  document.getElementById("fit-btn").addEventListener("click", fitGraph);
  document.getElementById("clear-btn").addEventListener("click", clearFocus);
  svg.addEventListener("click", clearFocus);
  svg.addEventListener("wheel", onWheel, {{ passive: false }});
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
  layers.edges.textContent = "";
  layers.nodes.textContent = "";
  layers.labels.textContent = "";
  layers.ideaLabels.textContent = "";

  for (const idea of DATA.ideas) {{
    const path = el("path", {{"class": "idea-hull", fill: idea.color, stroke: idea.color, "data-id": idea.id}});
    path.addEventListener("click", ev => {{ ev.stopPropagation(); focusIdea(idea.id); }});
    path.addEventListener("mousemove", ev => showTip(ev, `<div class="id">${{escapeHtml(idea.id)}}</div><b>${{escapeHtml(idea.label)}}</b>`));
    path.addEventListener("mouseleave", hideTip);
    layers.hulls.appendChild(path);
  }}

  for (const edge of DATA.edges) {{
    const path = el("path", {{"class": `edge ${{edgeClass(edge.residual)}}`, "data-source": edge.source, "data-target": edge.target}});
    path.addEventListener("mousemove", ev => showTip(ev, edgeTip(edge)));
    path.addEventListener("mouseleave", hideTip);
    layers.edges.appendChild(path);
  }}

  for (const node of Object.values(nodeById)) {{
    const group = el("g", {{"class": `node ${{node.kind}}${{node.rewritten ? " rewritten" : ""}}${{node.context_filled ? " context-filled" : ""}}`, "data-id": node.id}});
    const shape = node.kind === "claim"
      ? el("circle", {{"class": "shape", r: 10, fill: node.color}})
      : el("rect", {{"class": "shape", x: -9, y: -9, width: 18, height: 18, rx: 2, fill: node.color}});
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
    label.textContent = `Idea ${{i + 1}}`;
    layers.ideaLabels.appendChild(label);
  }}
  renderPositions();
}}

function renderPositions() {{
  for (const path of layers.hulls.querySelectorAll(".idea-hull")) {{
    const idea = ideaById[path.dataset.id];
    path.setAttribute("d", hullPath(idea));
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
    label.setAttribute("x", avg(nodes, "x"));
    label.setAttribute("y", Math.min(...nodes.map(n => n.y)) - 36);
  }}
}}

function hullPath(idea) {{
  const nodes = [...idea.claim_ids, ...idea.evidence_ids].map(id => nodeById[id]).filter(Boolean);
  if (!nodes.length) return "";
  const pad = 40;
  const minX = Math.min(...nodes.map(n => n.x)) - pad;
  const maxX = Math.max(...nodes.map(n => n.x)) + pad;
  const minY = Math.min(...nodes.map(n => n.y)) - pad;
  const maxY = Math.max(...nodes.map(n => n.y)) + pad;
  const r = 26;
  return `M ${{minX + r}} ${{minY}} L ${{maxX - r}} ${{minY}} Q ${{maxX}} ${{minY}} ${{maxX}} ${{minY + r}} L ${{maxX}} ${{maxY - r}} Q ${{maxX}} ${{maxY}} ${{maxX - r}} ${{maxY}} L ${{minX + r}} ${{maxY}} Q ${{minX}} ${{maxY}} ${{minX}} ${{maxY - r}} L ${{minX}} ${{minY + r}} Q ${{minX}} ${{minY}} ${{minX + r}} ${{minY}} Z`;
}}

function avg(nodes, key) {{
  return nodes.reduce((sum, n) => sum + n[key], 0) / Math.max(1, nodes.length);
}}

function renderSide() {{
  document.getElementById("meta").innerHTML = `
    <span><b>${{DATA.claims.length}}</b> claims</span>
    <span><b>${{DATA.evidence.length}}</b> evidence</span>
    <span><b>${{DATA.edges.length}}</b> edges</span>
    <span><b>${{DATA.ideas.length}}</b> ideas</span>
  `;
  document.getElementById("score-grid").innerHTML = `
    <div class="score"><div class="v">${{metric(DATA.metrics.initial_residual)}}</div><div class="k">initial residual</div></div>
    <div class="score"><div class="v">${{metric(DATA.metrics.final_residual)}}</div><div class="k">final residual</div></div>
    <div class="score"><div class="v">${{metric(DATA.metrics.claim_rewrite_distance)}}</div><div class="k">rewrite distance</div></div>
  `;
  document.getElementById("papers").innerHTML = DATA.papers.map(p => `
    <div class="paper-row"><span class="paper-dot" style="background:${{p.color}}"></span><span>${{escapeHtml(p.label)}}</span></div>
  `).join("");
  document.getElementById("ideas").innerHTML = DATA.ideas.map((idea, i) => `
    <div class="legend-card" data-id="${{idea.id}}">
      <div class="legend-row">
        <span class="swatch" style="background:${{idea.color}}"></span>
        <div>
          <div class="legend-title">Idea ${{i + 1}} - ${{escapeHtml(idea.label)}}</div>
          <div class="legend-sub">${{idea.claim_ids.length}} claims, ${{idea.evidence_ids.length}} evidence, ${{idea.remaining_tensions.length}} tensions</div>
        </div>
      </div>
    </div>
  `).join("");
  for (const card of document.querySelectorAll(".legend-card")) {{
    card.addEventListener("click", () => focusIdea(card.dataset.id));
  }}
  renderDefaultDetail();
}}

function renderDefaultDetail() {{
  const high = DATA.edges.filter(e => e.residual >= 0.5).length;
  const mild = DATA.edges.filter(e => e.residual > 0 && e.residual < 0.5).length;
  const zero = DATA.edges.filter(e => e.residual === 0).length;
  document.getElementById("detail").innerHTML = `
    <h3>Reading the graph</h3>
    <p class="muted">Claims are circles, evidence pieces are squares. Edges show where a claim predicts at an evidence piece. Color shows residual after rewriting.</p>
    <div class="callout"><div class="k">Residual edge summary</div>${{zero}} agreement, ${{mild}} mild tension, ${{high}} strong tension.</div>
    <p class="muted">Click any Idea, claim, evidence piece, or edge-connected neighbor to focus the graph.</p>
  `;
}}

function focusIdea(id) {{
  if (state.focusType === "idea" && state.focusId === id) return clearFocus();
  state.focusType = "idea";
  state.focusId = id;
  renderIdeaDetail(ideaById[id]);
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
  state.focusType = null;
  state.focusId = null;
  renderDefaultDetail();
  applyFocus();
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
  if (state.focusType === "idea") return new Set(ideaById[state.focusId].member_ids);
  const set = new Set([state.focusId]);
  for (const edge of edgesByNode[state.focusId] || []) {{
    set.add(edge.source === state.focusId ? edge.target : edge.source);
  }}
  return set;
}}

function renderIdeaDetail(idea) {{
  document.getElementById("detail").innerHTML = `
    <h3>${{escapeHtml(idea.label)}}</h3>
    <p class="muted">${{escapeHtml(idea.scope.system)}}<br>${{escapeHtml(idea.scope.framework)}}</p>
    <h2>Claims</h2>
    <div class="pill-row">${{idea.claim_ids.map(id => pill(nodeById[id])).join("")}}</div>
    <h2>Evidence</h2>
    <div class="pill-row">${{idea.evidence_ids.map(id => pill(nodeById[id])).join("")}}</div>
    ${{idea.remaining_tensions.map(t => `<div class="callout bad"><div class="k">${{escapeHtml(t.edge_id)}}</div>${{escapeHtml(t.interpretation)}}<br><span class="mono">residual=${{metric(t.residual)}}</span></div>`).join("")}}
    ${{idea.open_questions.map(q => `<div class="callout"><div class="k">Open question - ${{escapeHtml(q.priority)}}</div>${{escapeHtml(q.question)}}<br><span class="muted">${{escapeHtml((q.suggested_next_steps || []).join(", "))}}</span></div>`).join("")}}
  `;
  wirePills();
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
  const rewrite = node.rewritten ? `<div class="callout"><div class="k">Rewrite</div>in/out strength ${{metric(node.x_in)}} / ${{metric(node.x_out)}}</div>` : "";
  const weaknesses = (node.weaknesses || []).map(w => `<li>${{escapeHtml(w)}}</li>`).join("");
  return `${{rewrite}}${{weaknesses ? `<h2>Weaknesses</h2><ul>${{weaknesses}}</ul>` : ""}}`;
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

function fitGraph() {{
  const nodes = Object.values(nodeById);
  const rect = svg.getBoundingClientRect();
  const minX = Math.min(...nodes.map(n => n.x)) - 90;
  const maxX = Math.max(...nodes.map(n => n.x)) + 90;
  const minY = Math.min(...nodes.map(n => n.y)) - 90;
  const maxY = Math.max(...nodes.map(n => n.y)) + 90;
  const scale = Math.min(rect.width / Math.max(1, maxX - minX), rect.height / Math.max(1, maxY - minY), 1.4);
  state.scale = scale;
  state.tx = (rect.width - (minX + maxX) * scale) / 2;
  state.ty = (rect.height - (minY + maxY) * scale) / 2;
  applyTransform();
}}

function applyTransform() {{
  layers.root.setAttribute("transform", `translate(${{state.tx}},${{state.ty}}) scale(${{state.scale}})`);
}}

function onWheel(ev) {{
  ev.preventDefault();
  const factor = ev.deltaY < 0 ? 1.08 : 0.92;
  const next = Math.max(0.45, Math.min(2.8, state.scale * factor));
  const rect = svg.getBoundingClientRect();
  const mx = ev.clientX - rect.left;
  const my = ev.clientY - rect.top;
  state.tx = mx - (mx - state.tx) * (next / state.scale);
  state.ty = my - (my - state.ty) * (next / state.scale);
  state.scale = next;
  applyTransform();
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
    ]
    paper_colors = {
        paper["paper_id"]: palette[i % len(palette)] for i, paper in enumerate(papers)
    }
    paper_labels = {
        paper["paper_id"]: _paper_label(paper) for paper in papers
    }
    claim_by_id = {claim["claim_id"]: claim for claim in claims}
    evidence_by_id = {ev["evidence_id"]: ev for ev in evidence}
    final_residual_by_edge = {
        item["edge_id"]: item for item in sheaf["residuals"]["final"]
    }

    claim_nodes = []
    for claim in claims:
        paper_id = claim["paper_id"]
        claim_nodes.append(
            {
                "id": claim["claim_id"],
                "short_id": claim["claim_id"],
                "kind": "claim",
                "label": claim["label"],
                "paper": paper_id,
                "paper_label": paper_labels.get(paper_id, paper_id),
                "color": paper_colors.get(paper_id, "#64748b"),
                "x_in": claim["x_final"][0],
                "x_out": claim["x_final"][1],
                "rewritten": bool(claim.get("rewrite_history")),
                "weaknesses": claim.get("weaknesses", []),
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
            }
        )

    idea_colors = ["#2563eb", "#0891b2", "#16a34a", "#d97706", "#7c3aed", "#be185d"]
    idea_nodes = []
    for i, idea in enumerate(ideas):
        member_ids = [*idea["contributing_claims"], *idea["contributing_evidence"]]
        idea_nodes.append(
            {
                "id": idea["idea_id"],
                "label": idea["title"],
                "color": idea_colors[i % len(idea_colors)],
                "claim_ids": idea["contributing_claims"],
                "evidence_ids": idea["contributing_evidence"],
                "member_ids": member_ids,
                "scope": idea.get("scope", {}),
                "remaining_tensions": idea.get("remaining_tensions", []),
                "tensions_resolved": idea.get("tensions_resolved", []),
                "open_questions": idea.get("open_questions", []),
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
