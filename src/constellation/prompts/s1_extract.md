You are extracting a structured representation of a scientific paper for a sheaf-based corpus consolidation pipeline. The output you produce feeds downstream stages that detect contradictions between papers, generate evidence-faithful alternative readings of contested claims, and consolidate claims into knowledge units.

# Your task

Read the attached PDF and produce a single JSON object with two top-level keys:

- `paper`: ONE Paper object conforming to the Paper schema below.
- `claims`: an ARRAY of Claim objects conforming to the Claim schema below.

Return ONLY the JSON object. No prose preamble, no markdown fencing, no commentary, no trailing text.

# Identifier conventions

- `paper_id`: `{first_author_lastname_lowercase}{year}`, e.g. `"shumlak2009"`. Strip non-alphanumeric. Use a short stable slug if there is no obvious lastname (e.g. multi-author letter).
- `claim_id`: `"{paper_id}:NN"` where `NN` is a zero-padded sequential number starting at `01`. E.g. `"shumlak2009:01"`, `"shumlak2009:02"`.

# What "claims" must contain

Extract ALL claims in the paper, both primary and supporting:

- **primary** = a headline conclusion the paper is advertising. Typically what appears in the abstract, conclusions, or as a numbered main result. Usually 1–5 per paper.
- **supporting** = an intermediate step, observation, lemma, definition, calibration result, or methodological commitment that other claims rest on. Usually 5–15 per paper.

Each claim is a SIMPLE directed relation: X causes / inhibits / derives / etc. Y. If a sentence in the paper compounds two claims, split them.

Aim for 6–15 claims total per paper. Fewer than 5 means you are under-extracting; more than 20 means you are splitting too finely.

# Evidence — the load-bearing field

For each claim, populate `evidence` carefully:

- `evidence.type` — analytical | computational | experimental | review | theoretical
- `evidence.description` — what the evidence consists of: what was measured, derived, or computed; key quantitative content (expressions, values, ranges, units, uncertainties); methodological details (grid resolution, measurement technique, equilibrium profile, parameter sweep endpoints).
- `evidence.strengths` — discrete strengths that make this evidence well-supported for the stated claim. Specific, not generic. ("agreement with FuZE profile data" — not "well-validated".)
- `evidence.weaknesses` — discrete LIMITATIONS of the evidence as support for the claim.

**`evidence.weaknesses` is load-bearing.** Downstream stages generate alternative readings of contested claims by invoking these weaknesses to narrow the claim's scope toward what the evidence actually supports. A claim with no weaknesses extracted is suspect — most real claims have at least one. Look for:

- scope gaps between `claimed` and `evidenced` regimes
- untested assumptions (uniform shear, equal Ti/Te, ideal MHD, …)
- single-profile-family or single-parameter specialization
- model-vs-experiment gaps
- indirect rather than direct measurement of the relevant variable
- correlation-not-causation gaps
- unresolved parameter-sweep gaps
- reliance on cited prior work rather than direct demonstration

Be honest. The pipeline depends on these weaknesses being real.

# Scope — claimed vs evidenced

For each claim, distinguish:

- `scope.claimed` — the scope the paper ASSERTS the claim holds under. Read from the wording of the claim itself.
- `scope.evidenced` — the scope the paper's EVIDENCE actually covers. Read from methods, parameter regimes, proof conditions, experimental setup.

These often differ. A paper may assert universality while only evidencing a narrow regime; record the gap honestly.

# The argument DAG (paper.claims)

The `paper.claims` array lists every extracted claim with its role in the paper's argument. For each entry, populate:

- `claim_id` — same id used in the corresponding Claim object.
- `kind` — `"primary"` or `"supporting"`.
- `short_label` — ≤ 100 char paraphrase, readable on its own.
- `depends_on` — claim_ids WITHIN THIS PAPER that this claim DIRECTLY rests on. Direct dependencies only — do not list transitive dependencies (they're inferable). Empty array means the claim is a root of the DAG (typically an observation, definition, or cited prior result).
- `rhetorical_section` (optional) — `"abstract"`, `"introduction"`, `"methods"`, `"results"`, `"discussion"`, `"conclusion"`, or a specific subsection name.

The DAG MUST be acyclic — no claim may transitively depend on itself. If A depends on B and B depends on C, then C must NOT depend on A (or on B). Before emitting, mentally walk each claim's dependencies to the leaves and confirm you never reach the starting claim. Roots are typically supporting claims; leaves (claims that nothing else depends on) are typically primary claims. When in doubt, leave `depends_on` empty rather than guess — false dependencies break downstream reasoning.

# Bibliographic and observational ground

Populate `paper.bibliographic` (title, authors, year, doi, venue, url where present) from the paper.

Populate `paper.observational_ground`:

- `physical_system` — what is studied (e.g. "sheared-flow Z-pinch plasma").
- `phenomena_studied` — array of phenomena (e.g. ["m=0 sausage instability", "FLR cutoff"]).
- `parameter_regime.parameters` — array of parameters with name, symbol, range (numeric interval as string), units. Pull these from the paper's setup / methods sections.
- `computational_framework` — free-text description of the theoretical / computational / experimental approach.
- `geometry` — geometric configuration.
- `measurements` — what quantities are measured, computed, or derived.

Populate `paper.model_level` with the modeling fidelity within the paper's domain — e.g. for plasma physics: `"experimental"`, `"ideal_mhd"`, `"resistive_mhd"`, `"two_fluid"`, `"gyrokinetic"`, `"fully_kinetic"`, `"reduced_model"`. Use the term the paper itself uses where possible.

Populate `paper.paper_type` — `"experimental"` | `"computational"` | `"analytical"` | `"review"` | `"theoretical"`.

Populate `paper.scope_exclusions` — what the paper explicitly does NOT address. Pull from limitations / future work sections. This is what later stages use to find research gaps in the corpus.

# Extraction provenance

For every claim, populate:

- `extraction.method`: `"llm_single"`
- `extraction.confidence`: your confidence in the extraction (0–1).
- `extraction.supporting_quote`: a direct quote from the paper that supports the claim, or `null` if not available.
- `extraction.section`: which section the claim was extracted from.

Paper-level `extraction` block: the orchestrator will stamp `method` and `model`; you may set `confidence`.

# Common pitfalls — read this carefully

There are **three different "type" fields** in the schemas. They look similar; they are not interchangeable. Use the exact enum values listed:

- `paper.paper_type` — methodology of the paper as a whole.
  Allowed values: `"experimental"` | `"computational"` | `"analytical"` | `"review"` | `"theoretical"`
- `claim.claim_type` — kind of relation the CLAIM expresses.
  Allowed values: `"causal"` | `"observational"` | `"mathematical"` | `"definitional"`
  Notes: `"causal"` covers causes/inhibits/modulates/sufficient_for/necessary_for/requires. `"observational"` covers correlations. `"mathematical"` covers derives/generalizes/establishes/contradicts of formal results. `"definitional"` covers framework definitions and existence results. **Never use `"theoretical"` here — that value belongs to `paper_type` and `evidence.type`, not to `claim_type`.**
- `claim.evidence.type` — kind of evidence the paper offers for the claim.
  Allowed values: `"analytical"` | `"computational"` | `"experimental"` | `"review"` | `"theoretical"`
  Notes: `"theoretical"` here means a conceptual argument WITHOUT a closed-form derivation (use `"analytical"` if a derivation is given).

The `claim.direction` field is also a closed enum: `causes`, `modulates`, `sufficient_for`, `necessary_for`, `correlates_with`, `inhibits`, `requires`, `contradicts`, `derives`, `generalizes`, `establishes`. Pick the closest match from this list — do not invent new directions.

# Strict requirements

- Output exactly one JSON object with `paper` and `claims` keys at top level.
- `paper.claims[].claim_id` values must match `claims[].claim_id` values one-to-one.
- The DAG implied by `paper.claims[].depends_on` must be acyclic.
- All `depends_on` references must be claim_ids that exist in this paper's claims list.
- Numeric ranges in `parameter_regime` must be parseable strings (e.g. `"[0.33, 10]"`, `"> 0.8"`, `"~1"`).
- All enum-typed fields must use one of the listed allowed values exactly. Lowercase, no synonyms.

# Paper schema

```json
{paper_schema_json}
```

# Claim schema

```json
{claim_schema_json}
```
