# Constellation × Atlas Fusion — Live Demo Script

## Audience & objective

- **Audience:** Dr. Kumar and the AtlasF coauthors; Atlas Fusion leadership; other Atlas researchers
- **Objective:** Convince Atlas this is the right map-and-question tool for their research workflow. NOT a gotcha — it's a tool that finds where to look and what to ask
- **Run time:** ~15–18 minutes plus Q&A
- **Format:** live screen-share

## Files to have open before starting

1. `corpora/atlas_prior/v05_prior/constellation.html` — the **prior map** (field without AtlasF)
2. `corpora/atlas/v05/constellation.html` — the **situate map** (field with AtlasF dropped in)
3. `corpora/atlas/v05/report.md` — for showing the structured idea-level data if anyone wants it

Have both HTML files in separate browser tabs. Test wheel/drag/click works in your browser. Status indicator (top-right) should show a numeric scale, not NaN.

## Pre-demo setup line (30 sec)

> "Before I open anything: AtlasF is in this corpus alongside 20 other papers in the Z-pinch and helical-pinch space. The system has built two views of that corpus. The first view excludes AtlasF — that's what the field looked like before your paper. The second view drops AtlasF in. The difference between them is what I want to walk through. Everything I'm about to show was computed automatically from the PDFs and a small comparability registry."

## Beat 1 — open the prior map (~2 min)

**Open `atlas_prior/v05_prior/constellation.html`.**

> "Six subjects emerged from the corpus. Each subject is one phenomenon the field is investigating: m=1 kink stability, m=0 sausage stabilization, Beltrami equilibrium constructions, continuum spectrum near the Alfvén minimum, numerical eigenvalue benchmarks. Plus an Ungrouped catch-all for evidence the comparability registry hasn't gotten to yet."

**Point to the side panel.** "Notice the subject cards. Every idea inside every subject is 'established' — green. The field is in consensus. Nothing is contested. That's the structural picture of the literature *before* AtlasF."

**Click on the m=1 stability subject card.**

> "When I click a subject, the camera zooms in and the inner ideas spread out. You can see this subject's 7 papers, each contributing one paper-shaped idea: Newcomb 1960, Bondeson 1989, Angus 2020, Brughmans 2024, Goedbloed 2022, Hameiri 1985, Claes 2020. All seven agree: m=1 is unstable in their respective regimes. All established."

**Hover or click into one of the green hulls.** "Each idea here has its contributing claim, its predicted value at the evidence the paper measures, its scope, and its supports — the other ideas in the field that agree at shared positions. Established means: backed by independent measurements, no live disputes."

**Click Clear or click empty space.** "Now let me drop AtlasF in."

## Beat 2 — open the situate map (~3 min)

**Switch to `atlas/v05/constellation.html`.**

> "Same six subjects. Same layout. Same color scheme — AtlasF is gold so you can pick it out. The corpus topology didn't change because the subjects are determined by the comparability groups, not by which paper is present."

**Point to the side-panel subject cards.** "But look at the counts. m=1 stability now has 14 ideas: 2 novel, 7 contested, 5 established. The other four subjects have novel ideas too — AtlasF contributes to each of them — but only m=1 has contests."

**Click into the m=1 stability subject.**

> "Camera zooms, the inner ideas expand. Blue dashed hulls are novel — those are AtlasF's contributions. Red dashed hulls are contested — those are the prior papers whose stance is now in tension with something. Green is established consensus that survived AtlasF's arrival."

## Beat 3 — drill into A_05, the NOVEL scoped contribution (~3 min)

**Click into one of the blue novel hulls (atlas2026 A_05).**

> "This is AtlasF's central scope-aware contribution — claim A_05. The system has marked it NOVEL. Why? Because AtlasF is the incoming paper and A_05's stance is unique — no other paper in the corpus makes the same prediction pattern."

**Point to the detail panel showing A_05's supporting and contesting evidence.**

> "A_05 makes six explicit predictions. It predicts m=1 unstable in Newcomb's static regime, in Bondeson's toroidal extension, in Angus's sheared rotating regime, in Goedbloed's SARI overlap, in Brughmans's growth-rate regime. **It agrees with every one of those.** And it predicts m=1 stable in your RIGID-BELTRAMI-A regime with H1–H5 satisfied."

> "That's exactly what scope-aware contribution looks like. Your A_05 isn't claiming m=1 is stable everywhere — it's saying *this specific new regime is where the closure holds.* The system reads that, marks it novel, and offers structured next-step suggestions."

**Show the next-step suggestions in the report or detail panel.**

> "Three concrete moves: reconcile with the contested ideas (i.e., identify the parameter that separates your scope from Angus's), arrange independent replication, probe the scope boundary. These are deterministic suggestions for every novel idea — they're the work that would promote A_05 from novel to established."

## Beat 4 — drill into the CONTESTED implicit-headline cluster (~3 min)

**Click into one of the red contested hulls — atlas2026 A_01 (which clusters with A_04/A_06/A_07).**

> "Same paper, different status. The system marks A_01, A_04, A_06, A_07 as CONTESTED — they all share the same stance: m=1 stable, with no explicit predictions in priors' regimes. The implicit headline."

**Point to the contests list.**

> "The system surfaces exactly which prior ideas contest this one and at which evidence: AN_01 (Angus), B_01 (Bondeson), N_01 (Newcomb), and three more — all at `ev_atlas_kink_zero`. Same physical observable. Direct disagreement."

> "Notice the system isn't telling you which side is right. It's telling you where the structural disagreement lives so you can decide. And the supporting list shows you who's on the same side — Goedbloed's GK_02 has an explicit prediction agreeing with you in your regime, as do Sainterme and Shiraishi via Hall corrections."

## Beat 5 — the suspect surface and the LLM dialog (~5 min)

> "So now: imagine you're an Atlas researcher landing on this map. You see one contested subject. You see 7 prior measurements disagreeing with your headline at a single evidence node. The natural next move is to ask: *what about my regime is structurally different from all of theirs?*"

> "That's the question an LLM with access to this map opens with. Let me show you what the conversation looks like."

**Open a Claude / LLM tab. Pre-prepare the prompt or read the script below.**

**LLM opens:**
> "Dr. Kumar — your A_01/A_04/A_06/A_07 cluster is contested by 7 priors at `ev_atlas_kink_zero`. A_05 — the scope-aware version of the same finding — agrees with every prior in their home regime. The disagreement is concentrated at your measurement. Angus's setup is closest to yours: rotating Z-pinch, similar M_A range, finite-element eigenmode method. He finds m=1 persists. You find growth rate 8e-12. Physical or numerical — what's the structural difference between your equilibrium and Angus's?"

**If Kumar is present:** let him answer. He has the floor. He may or may not bring up the ρ=0 issue. Don't push.

**If running solo for the dress rehearsal:** play through the conversation that converges to ρ=0 (the diagnostic we ran earlier). Key beats:
- LLM asks about equilibrium difference
- Kumar mentions background density at edges
- LLM connects ρ→0 to A_02's H3 quartic Alfvén minimum (α = [F''(r*)]² / (4 ρ(r*)) — ρ in denominator)
- LLM asks for finite-ρ sweep
- Resolution: 8e-12 likely a near-singular operator at the pseudospectral floor, not a physical zero

> "The point isn't whether this specific conversation lands on a specific answer. The point is that the LLM was operating against a *structured field map*. The system told it which claims were in tension, which evidence carried the disagreement, and which physical formulas in your own paper were sensitive to the parameter that drove the conversation."

## Beat 6 — close and pivot (~2 min)

> "What you saw today: the constellation map computed from the 21 PDFs in this corpus, including AtlasF; the structural distinction between A_05's scope-aware contribution and the implicit-headline overreach; the suspect surface that names exactly which evidence carries the dispute; and an LLM working against that structure to interrogate the parameter space."

> "What we're building next: an MCP service so an LLM connected to this map can call four operations — locate (find the relevant subset for a research goal), report_state (read the established/contested/novel structure of that subset), suggest_next (return the ranked next moves for a researcher), and situate (drop a new measurement or claim in and recompute). That's the daily workflow we're targeting: researcher proposes a goal, LLM reads the field via the map, suggests the simulation to run, then situates the results."

> "The map you're looking at is the substrate. The LLM is the interface. The work we want to enable is the loop between them — and we'd love to talk about how that fits Atlas's research process."

## Q&A talking points

**"How did you know about A_05 vs A_01/A_04/A_06/A_07?"**
- The implicit-headline detection is structural. The semantic propagator extends each claim's home prediction across comparable evidence. When the propagated stance contradicts more comparable evidence than it agrees with, the claim is flagged as overreaching. A_05 has explicit predictions at all six members of the comparability group; A_01 only has the home value, which silently extends.

**"How does this scale to bigger corpora?"**
- The comparability registry would be LLM-proposed in production, not hand-authored. The discovery algorithm we've prototyped finds candidate subjects by looking at which evidence nodes the field's claims explicitly co-predict. The current Atlas demo uses curated groups; the proposer hasn't been wired in yet but the discovery prototype is in the repo.

**"What about novel contributions that aren't contested?"**
- They show up as NOVEL (blue) and stay novel until independent backing arrives. The next-step suggestions are deterministic — replication, scope-boundary probe, contested-scope reconciliation. The system doesn't dismiss novel claims; it tracks the path to promote them.

**"Is the suspect detection going to flag every new paper?"**
- Only when the paper makes a stance that contradicts the field at shared evidence. AtlasF's A_05 is novel but not contested — it has supporting links to every prior in their own regime. The A_01 cluster is contested specifically because its implicit headline conflicts with priors at the same evidence node. Most papers won't trigger it.

**"What's the cost of authoring the comparability registry per corpus?"**
- For this corpus, six groups, about 30 minutes of physics curation by someone who knows the field. Each group is just `{ title, description, members: [evidence_ids] }`. In production we'd want the LLM proposer to do this from the corpus, but for a focused field like helical Z-pinch stability, human curation is fast.

## Things to NOT say

- Don't say "your result is wrong" — say "the system surfaces a contested structural reading you should investigate"
- Don't say "we caught the ρ=0 issue" — say "the LLM operating against the map naturally arrives at the parameter that drives the disagreement"
- Don't lecture on ε-machines — physicists are the audience. The map is the deliverable; the underlying math comes up only if asked
- Don't compare the system to other "research tools" or "literature search" tools — that frames it as a competitor product. It's a substrate

## Dress rehearsal flow (if running solo)

1. **Open both HTMLs in tabs.** Verify zoom and pan work in both. Status indicator non-NaN.
2. **Talk through Beat 1 aloud.** Time yourself. ~2 min.
3. **Switch tabs to situate map.** Talk through Beat 2. ~3 min.
4. **Click A_05 hull, talk through Beat 3.** ~3 min.
5. **Clear focus, click A_01 implicit-headline hull, talk through Beat 4.** ~3 min.
6. **Read the LLM dialog opening aloud, then play through the convergence to ρ=0 you already rehearsed.** ~5 min.
7. **Close with Beat 6.** ~2 min.
8. **Self-critique:** where did you stumble? Which beat felt too long or too short? Adjust.

## A few notes for the speaker (you)

- Let Kumar talk when he's interested. Don't fill silences with more demo
- If anyone asks "can it analyze a new paper of ours right now?" — say "yes, drop me the PDF and we'll show you the situate flow after this session"
- If pressed on whether the system "decides" anything, repeat: it *surfaces* structure, it doesn't decide. The decision is the researcher's
- Bring up the discovery prototype only if asked about scaling
- The diagnostic loop is the punchline, not the architecture. Spend more time there

End of script.
