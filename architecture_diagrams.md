# Constellation — architecture diagrams

Each block is a Mermaid diagram. Render natively on GitHub/GitLab, paste into
Notion or Confluence, or open in https://mermaid.live to tweak.

---

## 1. Pipeline at a glance

Nine stages, run sequentially over a corpus. Stages that call the LLM are
gold; pure-code stages are blue. Each stage reads upstream artifacts from disk
and writes its own — any stage can be re-run in isolation with `--from N --to N`.

```mermaid
flowchart TD
    PDFs[("PDFs in corpora/&lt;name&gt;/pdfs/")]
    S1["1 Extract<br/>LLM · 1 call/paper<br/>→ papers/, claims/"]
    S2["2 Tag<br/>LLM · propose vocab + batched tagging<br/>→ tag_vocabulary.json, tags.json"]
    S3["3 Comparability complex<br/>CODE · regime ∧ mechanism overlap<br/>→ comparability_complex.json"]
    S4["4 Alternatives<br/>LLM · score originals, rewrite contested claims<br/>→ sheaf.stalks + edge scores"]
    S5["5 Compatibility cube<br/>LLM · variant×variant on contested edges<br/>→ sheaf.restriction_maps full"]
    S6["6 MAP section<br/>CODE · max coherence − λ·rewrite, with λ sweep<br/>→ sheaf.map_section, lambda_sensitivity"]
    S7["7 Frustration<br/>CODE · Penrose triangles, ρ<br/>→ sheaf.frustration"]
    S8["8 Consolidate<br/>LLM · ε-state partition → Ideas<br/>→ ideas/, epsilon_machine.json"]
    S9["9 Report<br/>CODE · synthesis<br/>→ report.md, constellation.html"]

    PDFs --> S1 --> S2 --> S3 --> S4 --> S5 --> S6 --> S7 --> S8 --> S9

    classDef llm fill:#fff4d6,stroke:#a86c00,color:#000
    classDef code fill:#dcecff,stroke:#1e6091,color:#000
    class S1,S2,S4,S5,S8 llm
    class S3,S6,S7,S9 code
```

---

## 2. What a run produces

JSON-on-disk is the source of truth at MVP. Every artifact is independently
inspectable.

```text
runs/<corpus>_<utc>/
├── run_config.json          ← model, schemas, prompt hashes, stage params
├── papers/<paper_id>.json   ← stage 1
├── claims/<paper_id>_NN.json← stage 1, with argument DAG
├── tag_vocabulary.json      ← stage 2a (semilattice + SNAG vocabulary)
├── tags.json                ← stage 2b (per-claim coordinates)
├── comparability_complex.json  ← stage 3 (the sheaf's base)
├── sheaf.json               ← stages 4–7: stalks, restriction maps,
│                                MAP section, λ sensitivity, frustration
├── ideas/<idea_id>.json     ← stage 8 (one ε-state per file)
├── epsilon_machine.json     ← stage 8 (Cμ + transition graph)
├── report.md                ← stage 9 (human-readable synthesis)
├── constellation.html       ← stage 9 (interactive D3 view)
├── failures.json            ← structured per-stage failures, when present
└── llm_cache/<stage>/<hash>.json  ← successful validated LLM responses
```

---

## 3. Object model

Four core object types plus the corpus-level ε-machine artifact.

```mermaid
classDiagram
    direction LR
    class Paper {
        paper_id
        bibliographic
        observational_ground
        model_level
        claims (argument DAG)
    }
    class Claim {
        claim_id, paper_id
        cause / effect / direction
        scope.claimed
        scope.evidenced
        evidence (strengths, weaknesses, quantitative)
        credibility_score
    }
    class Sheaf {
        base : claim_ids
        stalks : variants per claim
        restriction_maps : compatibility cube
        map_section : selected variant per claim
        frustration : ρ + Penrose triangles
        lambda_sensitivity : sweep results
    }
    class Idea {
        contributing_claims (with MAP variants)
        scope (meet of evidenced scopes)
        consensus
        frustration (intra-Idea ρ)
        transitions_in / transitions_out
        open_questions + suggested_next_steps
    }
    class EpsilonMachine {
        Cμ statistical_complexity_bits
        effective_states
        state_distribution
        transition_graph
    }

    Paper "1" --> "many" Claim : extracts
    Sheaf "1" --> "many" Claim : base over
    Sheaf "1" --> "many" Idea : partitions into
    Sheaf "1" --> "1" EpsilonMachine : derives
```

---

## 4. The core mechanic — worked example

The v2 innovation: claims aren't clustered first. Instead, each claim sits in
a *stalk* of evidence-faithful rewrites. A global MAP optimization picks one
variant per claim that maximizes pairwise compatibility minus rewrite cost.
Then surviving claims are partitioned into Ideas.

This worked example uses real claims from the small_atlas run.

### Step 1 — stage 4a: score original-original on every comparability edge

```mermaid
graph LR
    M3[mahajan2015:03 #original<br/>'helicity minimization yields Beltrami equilibria']
    Y4[yoshida2002:04 #original<br/>'helicity minimization is ill-posed;<br/>use enstrophy as target functional']
    M3 ==>|score −0.55<br/>kind: contradiction| Y4

    classDef contested fill:#ffd9d9,stroke:#a83232,color:#000
    class M3,Y4 contested
```

### Step 2 — stage 4c: generate evidence-faithful rewrites for each contested claim

```mermaid
graph TB
    subgraph stalkM3[Stalk over mahajan2015:03]
        M3a[#original<br/>helicity minimization yields Beltrami]
        M3b[#alt_conditioned_on_wellposedness<br/>'IF the variational problem is well-posed,<br/>THEN helicity min yields Beltrami'<br/>rewrite_distance 0.30<br/>invokes weakness: 'no proof of well-posedness']
    end
    subgraph stalkY4[Stalk over yoshida2002:04]
        Y4a[#original<br/>'helicity min ill-posed; use enstrophy']
    end

    classDef rewrite fill:#fff4d6,stroke:#a86c00,color:#000
    class M3b rewrite
```

### Step 3 — stage 6: MAP picks one variant per claim, globally

Maximize Σ score(selected_pair) − λ × Σ rewrite_distance over all claims.

```mermaid
graph LR
    sel["MAP section<br/><br/>selected[mahajan2015:03] = #alt_conditioned_on_wellposedness<br/>selected[yoshida2002:04] = #original<br/><br/>edge now scores +0.55 refinement<br/>(was −0.55 contradiction)"]

    classDef selected fill:#d4f4d4,stroke:#2d8a3a,color:#000
    class sel selected
```

### Step 4 — stage 8: partition MAP-selected claims into ε-states (Ideas)

```mermaid
graph TB
    idea[Idea 01<br/>'Multi-fluid Beltrami relaxation theory provides<br/>a variational framework for self-organized plasma equilibria<br/>with helical flows, but energy minimization under generalized<br/>helicity constraints is ill-posed without enstrophy as target']

    M3sel[mahajan2015:03<br/>#alt_conditioned_on_wellposedness]
    Y4sel[yoshida2002:04 #original]
    others[+ 24 other contributing claims<br/>across mahajan2015 and yoshida2002]

    M3sel --> idea
    Y4sel --> idea
    others --> idea

    classDef idea fill:#e0f0ff,stroke:#1e6091,color:#000
    class idea idea
```

---

## 5. Theoretical grounding

Three sources, each load-bearing in v2 (vs. v1 where they were inspirational).

```mermaid
graph LR
    sheaf[Sheaf theory<br/>Hansen-Ghrist · Robinson 2017]
    cdi[Coherence-driven inference<br/>Huntsman 2025]
    em[ε-machines<br/>Crutchfield-Shalizi]

    sheaf --> a[Stage 3 — comparability complex<br/>is the sheaf base]
    sheaf --> b[Stage 4 — stalks of variants<br/>are the sheaf sections]
    sheaf --> c[Stage 6 — MAP global section<br/>is nearest-to-global]
    sheaf --> d[Stage 6/7 — residual H¹<br/>is structural obstruction]

    cdi --> e[Stage 5 — pairwise scoring<br/>is local CDI]
    cdi --> f[Stage 6 — MAP optimization<br/>is global CDI with rewrite prior]

    em --> g[Stage 8 — ε-state partition<br/>becomes Ideas]
    em --> h[Stage 8 — epsilon_machine.json<br/>reports Cμ + transition graph]
```

---

## A few framing claims for the talk

- **The architectural shift** is replacing v1's cluster-first-then-check-coherence
  with sheaf-over-comparability-complex. Clustering is gone; coherence is global.
- **The hypothesis-space stalk** is the v2 unit of vote: MAP votes over *variants*
  of claims, with rewrite distance as the prior preventing free-for-all rewriting.
- **Residual H¹ is informative.** Edges where no rewrite within evidence-faithful
  distance resolves the contradiction are real obstructions in the literature,
  not failures of the pipeline.
- **The deliverable is Ideas + ε-transitions + open questions.** Each open
  question carries typed `suggested_next_steps` (experiment, simulation,
  theoretical, …) so a researcher can filter "what to work on next."
- **MVP scale** is 10–20 papers. Output is 3–10 Ideas. We've validated the full
  pipeline end-to-end on small_atlas (8 papers → 6–8 Ideas, Cμ ~2.5 bits, ρ &lt; 0.05).
