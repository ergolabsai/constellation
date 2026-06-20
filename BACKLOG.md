# Constellation — Azure DevOps Backlog

Flat list of Product Backlog Items, each with acceptance criteria and a small task breakdown. Grouped by area for skimming. Effort: T-shirt sizing (`XS`, `S`, `M`, `L`).

## Tagging convention

- **area:** `map`, `viz`, `mcp`, `demo`, `discovery`
- **kind:** `physics`, `ux`, `architecture`, `polish`

---

## Area: MAP (the substrate)

### PBI: Living-map snapshot store (M)

**Description:** Persist the corpus state and the derived map between runs so `situate` becomes an incremental operation rather than a full rebuild.

**Acceptance:**
- `corpus.lock.json` records which papers + claims + evidence the current map was built from
- `map.snapshot.json` records derived state (subjects, ideas, hygiene, stature)
- `run_pipeline` reads the snapshot if present and writes a fresh one
- A second `run_pipeline` call on the same corpus is a no-op (idempotent)

**Tasks:**
- Define schemas for `corpus.lock.json` and `map.snapshot.json`
- Add snapshot read/write in `pipeline.py`
- Add no-op detection (compare incoming corpus state to snapshot)
- Test: run twice, second run produces no diff

### PBI: Situate returns a structured diff (M)

**Description:** When a new paper drops into a corpus, the situate output should describe what changed structurally — not just rebuild artifacts.

**Acceptance:**
- New return shape: `{ideas_added, ideas_removed, status_changes: [...], contests_introduced: [...], supports_introduced: [...]}`
- An LLM can summarize this as "what changed in the field when X arrived"
- Round-trip test: situate AtlasF into atlas_prior, diff matches the established/contested/novel breakdown in the regenerated map

**Tasks:**
- Add diff computation between two map snapshots
- Define the JSON response shape
- Wire diff into the pipeline return value
- Test against the Atlas/atlas_prior pair

### PBI: Statistical-complexity stature signal (M)

**Description:** Replace "distinct backing papers" with a weighted signal — claims that predict more of the field's evidence count more.

**Acceptance:**
- New `compute_complexity_stature` alongside existing `compute_stature`
- Both signals exposed; sheaf output includes both
- A/B comparison: do established/contested/novel splits read differently?
- Decision: which signal becomes the default

**Tasks:**
- Define the complexity formula (surprise reduction over corpus)
- Implement function
- Add A/B comparison harness
- Document trade-off in `docs/STATURE_SIGNALS.md`

---

## Area: VIZ (HTML constellation map)

### PBI: Contests arrows between idea hulls (S)

**Description:** When two ideas in the same subject contest each other, draw a small arrow between their hulls so the disagreement is legible at a glance.

**Acceptance:**
- When a subject is focused and its inner hulls are visible, contests-arrows are drawn between contesting pairs
- Arrow style: subtle, dashed, red, double-headed
- Arrows dim with the rest of the subject when an inner idea is focused

**Tasks:**
- Read each idea's `contests` list during render
- Compute arrow endpoints from hull centers
- Add SVG arrow rendering layer
- Style arrows (dashed, double-headed, red)

### PBI: URL-routable focus state (S)

**Description:** The HTML viz should encode the focused subject and inner idea in the URL so a researcher (or LLM) can deep-link.

**Acceptance:**
- Focusing a subject updates `?subject=subject_NN_*`
- Focusing an inner idea adds `&idea=idea_*`
- Loading a URL with focus params applies focus on init
- Browser back/forward navigates between focus states

**Tasks:**
- Add URL params parser on init
- Update params on focus/clear
- Wire `popstate` listener for back/forward
- Test deep-link behavior

### PBI: Edge styling differentiates base vs semantic edges (XS)

**Description:** Semantic cross-edges (from implicit-headline propagation) are currently visually identical to base edges. They should look different.

**Acceptance:**
- Semantic edges render with a different stroke style (dotted vs dashed, or thinner)
- Legend includes a row explaining the distinction
- Hover tip on a semantic edge shows "(propagated)"

**Tasks:**
- Add `semantic: true` flag to the edge data
- Update SVG edge styling
- Update legend
- Update hover tip text

### PBI: Improve inner-hull overlap when many ideas share evidence (M)

**Description:** In the m=1 subject (14 ideas), inner hulls heavily overlap because many ideas include the same `ev_atlas_kink_zero` node. Bias the within-subject layout so ideas with similar status cluster.

**Acceptance:**
- Inside an expanded subject, established ideas cluster on one side, contested on another, novel on a third
- Overlap is reduced even when many ideas share a common member
- Behavior preserved when subject has only one idea status

**Tasks:**
- Add status-based positioning bias in `layoutNodes`
- Run on m=1 subject and verify visual separation
- Adjust spread / bias strength
- Verify other subjects unchanged

---

## Area: MCP (LLM-callable service surface)

### PBI: Spec the four MCP operations (S)

**Description:** Write the request/response schema for the four MCP operations the LLM workflow needs, before implementation begins. Unblocks downstream PBIs.

**Acceptance:**
- `docs/MCP_SPEC.md` exists with sections for `locate`, `report_state`, `suggest_next`, `situate`
- Each operation specifies: parameter schema, return schema, example call, error modes
- A team member can read the spec and implement the server against it without re-discussion

**Tasks:**
- Draft `locate` schema
- Draft `report_state` schema
- Draft `suggest_next` schema
- Draft `situate` schema (depends on snapshot store PBI being in flight)
- Review with the team

### PBI: MCP server scaffold (M)

**Description:** Python stdio MCP server in the repo style (zero-dep, pure Python). No operations implemented yet — just the scaffold.

**Acceptance:**
- `src/constellation/mcp_server.py` exists
- Server starts via `python -m constellation.mcp_server`
- Returns tool list when queried
- Logs requests and responses to stderr

**Tasks:**
- Add MCP stdio scaffold
- Wire tool-list response
- Add request/response logging
- Smoke test with `mcp` CLI

### PBI: Implement `locate(goal)` (M)

**Description:** Given a natural-language research goal, return the relevant subjects and matched keywords.

**Acceptance:**
- Takes a `goal: str` parameter
- Returns `{subjects: [subject_id, ...], scope_keywords: [str, ...]}`
- Matches subjects by keyword overlap with the goal text + claim labels
- Includes the corpus name in the response

**Tasks:**
- Write keyword extraction from goal string
- Score subjects by keyword overlap with each subject's scope
- Implement the MCP tool
- Test with sample goals: "find m=1 stabilization methods", "what's known about Beltrami equilibria"

### PBI: Implement `report_state(subject_id)` (S)

**Description:** Return the established/contested/novel breakdown for a subject. Existing data — just exposed as a tool.

**Acceptance:**
- Takes `subject_id: str`
- Returns `{established: [...], contested: [...], novel: [...], counts, structural_tensions}`
- Each idea entry includes title, contributing paper, scope, and key contested-with / supported-by relations

**Tasks:**
- Implement the MCP tool
- Add error handling for unknown subject_id
- Test against the Atlas situate map

### PBI: Implement `suggest_next(subject_or_idea_id)` (S)

**Description:** Return the ranked next-step suggestions. Existing data — just exposed.

**Acceptance:**
- Takes `subject_id` OR `idea_id`
- Returns the ordered list of `next_steps` from the subjects/ideas data
- For subjects, returns the subject-level open questions plus aggregate of inner-idea next_steps

**Tasks:**
- Implement the MCP tool
- Handle both subject and idea ids
- Test

### PBI: Implement `situate(new_claims, new_evidence)` (L)

**Description:** Drop new claims and evidence into the map and return the diff. Depends on snapshot store + diff PBIs in the Map area.

**Acceptance:**
- Takes lists of new claims and evidence in the standard JSON shapes
- Runs the situate pipeline (semantic propagation, optimizer, subject re-derivation)
- Returns the diff structure

**Tasks:**
- Wire snapshot read at start
- Run the situate pipeline
- Compute the diff
- Return the structured response
- Test with a small synthetic contribution

---

## Area: DEMO + CUSTOMER (Atlas Fusion launch)

### PBI: Dress rehearsal recording (XS)

**Description:** Record a solo run-through of the demo so you can self-review before the live session.

**Acceptance:**
- Screen + audio recording of the full ~15-minute demo
- Reviewed at least once; rough notes on where to tighten

**Tasks:**
- Set up recording
- Run through the demo solo
- Review and note adjustments

### PBI: Post-demo feedback capture form (XS)

**Description:** Short structured form to send Atlas after the demo so feedback doesn't depend on individuals remembering to email.

**Acceptance:**
- 3-question form (what worked, what didn't, what would you want next)
- Sent within 24 hours of demo
- Responses captured in a single document for team review

**Tasks:**
- Draft 3 questions
- Send to attendees
- Compile responses

### PBI: Atlas amendments to comparability registry (S)

**Description:** After the demo, capture any refinements Atlas suggests to the comparability groupings. Apply, regenerate, send back as evidence we listened.

**Acceptance:**
- Atlas's suggested registry changes captured
- Updated `corpora/atlas/comparability.json` reflects them
- Regenerated map artifacts sent to Atlas

**Tasks:**
- Capture suggestions during/after demo
- Update comparability.json
- Regenerate artifacts
- Send updated artifacts with a note

### PBI: Second-corpus onboarding runbook (M)

**Description:** Write down the steps for taking a new customer's PDFs and producing their first constellation map. Currently in your head.

**Acceptance:**
- `docs/CORPUS_ONBOARDING.md` covers: PDF intake, extractor seed authoring, comparability group curation, first situate, first demo
- A new team member could follow it to onboard a corpus without your help

**Tasks:**
- Write each section
- Test by hypothetically applying it to a non-Atlas corpus
- Get a review from a teammate

---

## Area: DISCOVERY (automate the hand-authored parts)

### PBI: Port discovery prototype into src/constellation (M)

**Description:** The `prototype/discover_ideas.py` prototype works. Port the (group, value) bucket discovery into a real module so a `--discover` flag becomes possible.

**Acceptance:**
- `src/constellation/discover.py` exists
- `discover_comparability_groups(claims, evidence) -> dict` returns the same shape as authored `comparability.json`
- Pipeline accepts a `discover=True` flag that uses discovered groups instead of authored

**Tasks:**
- Move discovery logic from prototype to src
- Add the pipeline flag
- Smoke test: run pipeline with discover=True on Atlas
- Document in `docs/DISCOVERY.md`

### PBI: Discovered-vs-authored comparison harness (S)

**Description:** A small reporting tool that compares discovered groups to authored groups and reports overlap/coverage.

**Acceptance:**
- `prototype/discover_vs_authored.py` runs both and prints: per-group IoU, members missed by discovery, extra groups discovery found
- Output is human-readable
- Run as part of pre-demo prep on Atlas to ensure no regression

**Tasks:**
- Implement comparison logic
- Format output
- Add to CI or pre-demo checklist

### PBI: LLM-named discovered groups (M)

**Description:** When the discovery algorithm proposes a group, have an LLM generate its `title` and `description` from the member labels.

**Acceptance:**
- Discovered groups now have human-readable titles (instead of "discovered_group_03")
- Same Claude call works for arbitrary new corpora
- Cached per group signature so re-runs don't re-call

**Tasks:**
- Write the naming prompt
- Integrate the LLM call
- Add caching
- Test on the Atlas discovered groups

---

## Suggested next sprint (2 weeks)

In rough priority order:

1. **Spec the four MCP operations** (S) — unblocks all MCP implementation
2. **MCP server scaffold** (M) — minimum harness so subsequent PBIs slot in
3. **Implement `report_state`** (S) — quickest demonstrable MCP win, exposes data we already have
4. **Implement `locate`** (M) — pairs naturally with report_state for an end-to-end LLM demo
5. **Living-map snapshot store** (M) — gating dependency for the `situate` MCP operation
6. **Post-demo feedback capture form** (XS) — should happen the day of the demo
7. **Atlas amendments to comparability registry** (S) — capture and apply within a week of demo

Total estimated effort: roughly 2 small + 4 medium + 1 large = realistic for a 2-week sprint with a small team. Drop `situate` to the following sprint if needed.

---

## Already shipped (this iteration — for velocity history if useful)

- Two-layer subjects + lifecycle ideas (established/contested/novel)
- Stature-weighted optimizer (epistemic cost flip)
- Semantic cross-paper edges + implicit-headline detection
- Per-claim hygiene classification
- Interactive HTML viz: subject hulls, click-to-expand, inner idea hulls, zoom, pan, drag
- Atlas demo materials (DEMO_SCRIPT.md + regenerated artifacts)
- Stable per-paper / per-subject colors across runs
- Universal next-step suggestions for every subject and every idea

End of backlog.
